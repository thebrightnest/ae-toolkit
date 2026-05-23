# Approval Checkpoint

Hard gate between design discussion and implementation. Use this command whenever you are about to transition from proposing a design/plan to writing or modifying files.

## When to Use

- The user has just approved a design proposal ("yes", "sounds good", "go ahead", etc.)
- You are about to write, edit, or delete files based on that approval
- You are transitioning from any planning/design mode to implementation mode

## Procedure

1. **Enumerate changes.** List every file you intend to modify, create, or delete:

   ```
   Files to modify:
   - path/to/file1.ext (reason)
   - path/to/file2.ext (reason)
   ```

2. **Estimate scope.** State the approximate magnitude:

   ```
   Estimated scope: ~N files, ~M lines changed
   ```

3. **Ask for explicit approval.** Use exactly this format:

   ```
   ⚠️ Implementation checkpoint

   I will modify the files listed above.
   Approve to proceed, or request changes first?
   ```

4. **Hard gate:** Do not write, edit, or delete any file until the user explicitly responds with approval language ("approve", "go ahead", "do it", "proceed", "yes" to the checkpoint itself).

5. **If the user requests changes:** Revise the proposal and return to step 1.

## Anti-Patterns

- ❌ Treating "yes" to a high-level design question as approval to immediately edit files
- ❌ Starting implementation while the user is still reviewing the proposal
- ❌ Hiding scope by not listing all affected files
