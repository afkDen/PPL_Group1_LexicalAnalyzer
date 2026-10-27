# Example corpus

These programs are specification fixtures, not claimed to execute yet. `manifest.json` records the phase when each must become executable/checkable, expected stdout (including escaped NUL), and expected error code. The current bootstrap test verifies coverage of every `.tfd` file, not language acceptance. M04 must parse all fixtures; M06/M07 validate their types/graphs; M09/M12 activate execution assertions. Never mark these tests passed by skipping all source execution after their owning milestone.

Start with `intro/hello.tfd`, then `intro/counter.tfd`. `features/snapshot_swap.tfd` distinguishes old-state reads from sequential assignment; `dependency_order.tfd` exposes the candidate graph. `guard_short_circuit.tfd` and `boundaries/candidate_fault.tfd` deliberately show different fault orders. `showcase/branching_inventory.tfd` combines modules, nominal data, scheduled proposals, rejection, delayed output, and branching from a retained snapshot.

The showcase expected transcript lives in the manifest; `models/shelf.tfd` is a library root checked without main. `invalid/` programs are expected to fail semantic checks, not be repaired into valid examples.
