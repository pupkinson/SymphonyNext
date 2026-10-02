"""Separate owner transition for two lost images with a preserved pinned seed."""
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from snci.common import canonical, decode, require, sha256, write_new
from snci.source import changed_paths
from snci import refresh

SOURCE_BASE = '716d3b5b6f22e6ebe005d09820ed8806667a287b'
SOURCE_TREE = '756497ffe84de4c8dbc7bff19cd7079296340bc8'
SEED = 'sha256:a93a7c8e7a2d292c924f461d06a27986b1a95818c1be1fbb5b68b290b409256c'
LOST = {
    'main': 'sha256:b6ef7528c8e8435208c0856698d50158e545c2e4fc7624ca6bda49f585a392c0',
    'sn004': 'sha256:9233988cb5fbbf405a565fc1d0bb92e9296e189b90f3381c50221463801a1172',
}
DELTA = {refresh.PREFIX + p for p in ('snci/refresh.py', 'snci/rebuild_missing.py',
                                    'tests/test_rebuild_missing.py', 'README.md')}


def package(old, reviewed, new):
    require(set(changed_paths(new, reviewed)) == DELTA, 'rebuild_package_scope')
    return refresh.package_delta(old, new, delta=refresh.DELTA | DELTA)


def image_tag(head, name):
    require(isinstance(head, str) and re.fullmatch(r'[0-9a-f]{40}', head)
            and name in LOST, 'rebuild_tag_identity')
    return 'localhost/symphony-next-ci-prepared:' + head + '-' + name


def seed_identity(owner):
    require(owner.SEED == SEED, 'rebuild_seed_pin')
    info = owner.inspect_image(SEED)
    require(info.get('Id') == SEED, 'rebuild_seed_identity')
    return dict(id=SEED, reference='localhost/symphony-next-ci-seed:' + SEED.split(':')[1],
                layers=owner.image_layers(info))


def preflight(owner, head, profiles):
    require(len(profiles) == 2 and {p['name']: p['image'] for p in profiles} == LOST,
            'rebuild_lost_image_binding')
    for name, image in LOST.items():
        require(owner.inspect_image(image, missing_ok=True) is None, 'rebuild_image_not_missing')
        require(owner.inspect_image(image_tag(head, name), missing_ok=True) is None, 'rebuild_tag_exists')
    seed = seed_identity(owner)
    receipts = {}
    for name in LOST:
        path = refresh.STATE / ('prepare-' + name) / 'seed.json'
        raw = refresh.trusted(path, private=True).read_bytes()
        require(decode(raw) == seed, 'rebuild_seed_receipt')
        receipts[name] = sha256(raw)
    return dict(seed=seed, seed_receipts=receipts)


def build(owner, root, profile, snapshot, head):
    require(seed_identity(owner) == snapshot['seed'], 'rebuild_seed_changed')
    tag = image_tag(head, profile['name'])
    require(owner.inspect_image(tag, missing_ok=True) is None, 'rebuild_tag_exists')
    write_new(root / 'Dependency.Dockerfile', snapshot['recipe'])
    write_new(root / '.dockerignore', b'*\n!Dependency.Dockerfile\n!source\n!source/**\n')
    print('REBUILD_IMAGE_START ' + profile['name'], flush=True)
    image = owner.build_dependency_image(root)
    require(isinstance(image, str) and re.fullmatch(r'sha256:[0-9a-f]{64}', image), 'rebuild_image_id')
    require(decode(refresh.trusted(root / 'seed.json', private=True).read_bytes()) == snapshot['seed'],
            'rebuild_build_seed')
    owner.verify_seed_build(snapshot['seed'], image)
    # Catch observable conflicts. Docker tag has no compare-and-set: the owner
    # must reserve this namespace for the workflow serialized by controller.lock.
    require(owner.inspect_image(tag, missing_ok=True) is None, 'rebuild_tag_exists')
    owner.run(owner.runner.DOCKER + ['image', 'tag', image, tag], timeout=30)
    require(owner.inspect_image(tag).get('Id') == image, 'rebuild_tag_readback')
    write_new(root / 'retention.json', canonical(dict(tag=tag, image=image)))
    return dict(profile, image=image)


def recheck(owner, snapshot, head, attempt, profiles):
    require(seed_identity(owner) == snapshot['seed'], 'rebuild_seed_changed')
    require(len(profiles) == 2 and {p['name'] for p in profiles} == set(LOST), 'rebuild_profiles')
    for profile in profiles:
        name = profile['name']
        raw = refresh.trusted(refresh.STATE / ('prepare-' + name) / 'seed.json', private=True).read_bytes()
        require(sha256(raw) == snapshot['seed_receipts'][name], 'rebuild_seed_history_changed')
        root = attempt / name
        require(refresh.trusted(root / 'Dependency.Dockerfile', private=True).read_bytes() == snapshot['recipe']
                and refresh.trusted(root / 'image.id').read_text().strip() == profile['image'],
                'rebuild_build_receipt')
        require(decode(refresh.trusted(root / 'seed.json', private=True).read_bytes()) == snapshot['seed'],
                'rebuild_build_seed')
        tag = image_tag(head, name)
        require(decode(refresh.trusted(root / 'retention.json', private=True).read_bytes())
                == dict(tag=tag, image=profile['image']), 'rebuild_retention_receipt')
        require(owner.inspect_image(tag).get('Id') == profile['image'], 'rebuild_tag_readback')
        owner.verify_seed_build(snapshot['seed'], profile['image'])


if __name__ == '__main__':
    refresh.main(rebuild=True)
