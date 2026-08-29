# Firebase Distribution

Daemon desktop clients use Firebase Authentication and Firestore REST access. Desktop clients must never contain a Firebase service-account JSON file.

## Production Setup

1. Create or select the Firebase project.
2. Enable Email/Password in Firebase Authentication.
3. Create the Firestore database.
4. Deploy `firestore.rules`:

```powershell
npx -y firebase-tools@latest deploy --only firestore:rules
```

5. Restrict the Firebase Web API key in Google Cloud to the Firebase Authentication Identity Toolkit API and Firestore API. The key is public client configuration, not an authorization credential.
6. Put the public project ID and API key in the release configuration template or inject them during the release build. Never put a UID, ID token, refresh token, or service-account key in that template.

## Runtime Behavior

- First launch shows Firebase email/password sign-in or account creation.
- The Firebase UID comes only from the authenticated token response.
- Firestore requests carry the current ID token as a bearer token.
- Data paths are scoped to `users/{uid}` and `users/{uid}/pets/{petId}`.
- `--no-auth` disables cloud access and runs local-only.
- Windows refresh-token files use DPAPI. Existing legacy plaintext token files are read for migration and rewritten in protected format on the next save.
- Sign out is available from the pet context menu. It stops cloud sync and removes the local auth token.

## Release Checklist

- Build from a clean checkout.
- Do not copy repository `data/` into `dist/`.
- Do not ship `firebase-credentials.json`, `.daemon_auth.json`, or developer config.
- Confirm packaged storage resolves under `%LOCALAPPDATA%\\Daemon`.
- Test registration with a new staging account.
- Restart and verify token refresh restores only that account's data.
- Sign out, sign in as a second account, and verify the first account's data is not visible.
- Test offline startup with `--no-auth`.
- Inspect the PyInstaller archive before distribution.

## Security Rules

Rules require `request.auth != null` and `request.auth.uid == uid` for user documents, pet documents, and diary entries. A client cannot bypass this with a different `petId`; changing `petId` only selects another private document under the same authenticated UID.

Rules must be tested against the Firebase Emulator Suite before production deployment. Minimum cases: unauthenticated read/write denied, same-user access allowed, and cross-user read/query/create/update/delete denied for user documents, pet documents, and diary entries.
