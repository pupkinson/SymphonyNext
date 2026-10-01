# Continuous CI cache-transfer repair

Status: owner-approved bounded repair, not product admission or runtime acceptance.
Base: `4662fbb392f531c59cb3ac07b4753ad353423a9f`, PR #19.

The worker dereferences `_build` links before removing its own compiled
application. Phoenix colocated output can contain a link to absent
`assets/node_modules`. Exclude `symphony_elixir` before copying from the
`dev` and `test` `lib` and `phoenix-colocated` directories. Keep dependency
links strict and retain the project PLT and its hash. Rebuild the application.
The first native exception is unknown; this source defect is independently
reproducible and must not be reported as a proven native traceback.

1. Record exact inputs and baseline; preserve all preceding attempts.
2. Add real filesystem regressions for own-application links, dependency
   failure, PLT invariance and tracked source invariance. Save RED, then
   implement the minimal cache filter.
3. Add closed setup-step diagnostics, with no exception text or filenames;
   test the actual error-to-runner transport and reject unknown fields/steps.
4. Add a separate single-use owner helper anchored to this base and exact
   unaccepted setup failure. Validate the installed package, policy, source,
   image and PLT receipts before moving evidence. Reuse the existing
   preparation driver, never its consumed `apply` operation. Reuse main's
   warm image and keep the timer disabled. Start SN004 only after main has
   a valid acceptance receipt.
5. Run the complete continuous CI local suite and static checks. Publish the
   related source delta to the existing PR without force. Obtain a fresh
   exact-HEAD review from the same independent read-only reviewer.
6. Hand off the exact reviewed helper bytes to the owner's existing root
   session. One native main attempt is authorized; stop on failure, preserve
   evidence, and report native acceptance only after authoritative readback.

No locked profile, recipe, capability, threshold or deadline changes.
No trusted status publication, activation, merge, deployment, extra reviewer
or new privilege. Rollback before native execution preserves the previous
installed package; a consumed attempt is never reset or automatically replayed.
