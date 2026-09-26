import base64
import importlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

class GitHubTests(unittest.TestCase):
    def setUp(self):
        try:self.api=importlib.import_module('github_api')
        except ImportError:self.fail('GitHub transport implementation is missing')
    def test_jwt_is_signed_and_does_not_embed_private_key(self):
        with tempfile.TemporaryDirectory() as d:
            key=Path(d)/'app.pem';pub=Path(d)/'pub.pem'
            subprocess.run(['openssl','genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:2048','-out',str(key)],check=True,capture_output=True)
            subprocess.run(['openssl','pkey','-in',str(key),'-pubout','-out',str(pub)],check=True,capture_output=True)
            jwt=self.api.make_jwt(123,key,now=1000)
            h,p,s=jwt.split('.')
            self.assertEqual(json.loads(base64.urlsafe_b64decode(p+'='*(-len(p)%4))),{'iat':940,'exp':1540,'iss':'123'})
            self.assertEqual(json.loads(base64.urlsafe_b64decode(h+'='*(-len(h)%4)))['alg'],'RS256')
            sig=Path(d)/'sig';sig.write_bytes(base64.urlsafe_b64decode(s+'='*(-len(s)%4)))
            result=subprocess.run(['openssl','dgst','-sha256','-verify',str(pub),'-signature',str(sig)],input=(h+'.'+p).encode(),capture_output=True)
            self.assertEqual(result.returncode,0)
    def test_transport_rejects_header_injection_and_foreign_path(self):
        for token,path in [('abc\nX: bad','/app'),('abc','https://example.org'),('abc','//example.org'),('abc','/app\n')]:
            with self.subTest(token=token,path=path),self.assertRaises(ValueError):
                self.api.CurlTransport(Path('/unused')).request('GET',path,token)
    def test_installation_scope_cannot_include_other_repositories(self):
        good={'id':123,'account':{'login':'pupkinson'},'repository_selection':'selected',
              'permissions':{'metadata':'read','contents':'read','pull_requests':'read','checks':'write'}}
        self.api.validate_installation(good,123)
        for key,val in [('id',124),('account',{'login':'other'}),('repository_selection','all'),
                        ('permissions',dict(good['permissions'],administration='write'))]:
            r=dict(good);r[key]=val
            with self.subTest(key=key),self.assertRaises(ValueError):self.api.validate_installation(r,123)

