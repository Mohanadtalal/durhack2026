# Four-person workflow

1. Clone the repository; follow README setup once.
2. Create your own branch from main: `git switch -c feat/your-feature`.
3. Prefer changes within your owned module; communicate before changing the incident API contract.
4. Commit regularly: `git add . && git commit -m "feat: description"`.
5. Push: `git push -u origin feat/your-feature`; open a PR on GitHub targeting `main`.
6. Have one teammate review, then merge. Refresh your branch using `git fetch origin` and `git merge origin/main`.
7. Run backend/edge tests and the frontend build before merging.
8. Never commit API keys, MongoDB credentials, camera footage of other people, or local `.env` files.

## Contract ownership

- Edge sends incidents using `POST /api/events`, not direct MongoDB writes.
- Backend owns `backend/app/models.py`, the stable data model.
- Gemini reads stored incidents only; it never triggers the local alarm.
- Dashboard uses API responses; it must not show fake incidents as real.
- Hardware warnings are independent of LLM/backend availability.

## Suggested check-ins
Hours 2, 6, 11, 16 and 19; freeze new features by hour 19 and leave three hours for integration, testing, and presentation.
