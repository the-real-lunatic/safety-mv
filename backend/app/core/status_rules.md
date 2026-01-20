# Job Status Transition Rules

- queued -> running, canceled
- running -> completed, failed, canceled
- completed -> (terminal)
- failed -> (terminal)
- canceled -> (terminal)

Notes:
- `queued` can be canceled before any work starts.
- `running` can be canceled by user or fail on error.
- Terminal states do not transition further.
