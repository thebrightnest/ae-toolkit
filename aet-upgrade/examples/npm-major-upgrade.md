# Example: npm Major Version Upgrade

## Context

- **Dependency:** `react-router-dom`
- **Current:** `^5.3`
- **Target:** `^6.0`
- **Package manager:** npm

## Breaking Changes Enumerated

### 1. `<Switch>` removed, replaced by `<Routes>`

**Description:** React Router v6 removed the `<Switch>` component. All `<Switch>` usage must be replaced with `<Routes>`, and `<Route>` children can no longer be components — they must use the `element` prop.

**Grep evidence:**

```bash
$ rg "<Switch" src/ --type tsx
src/App.tsx
23:      <Switch>
24:        <Route path="/" component={Home} />
25:        <Route path="/about" component={About} />
26:      </Switch>

src/components/AuthRouter.tsx
12:      <Switch>
13:        <Route path="/login" component={Login} />
14:      </Switch>
```

**Risk:** **High** — Found in 2 files, 4 `<Switch>` instances. No automated tests cover route rendering. Broken routing is a user-facing regression.

**Mitigation:**

- Replace all `<Switch>` with `<Routes>`
- Convert `<Route component={X} />` to `<Route element={<X />} />`
- Add a smoke test that visits `/`, `/about`, and `/login` and asserts the correct page renders

### 2. `useHistory` removed, replaced by `useNavigate`

**Description:** The `useHistory` hook is removed. All programmatic navigation must use `useNavigate`.

**Grep evidence:**

```bash
$ rg "useHistory" src/ --type tsx
src/hooks/useAuth.ts
18:  const history = useHistory();
19:  history.push('/dashboard');
```

**Risk:** **Medium** — Found in 1 file with 2 usages. Covered by auth integration tests.

**Mitigation:**

- Replace `useHistory` with `useNavigate`
- Replace `history.push('/dashboard')` with `navigate('/dashboard')`
- Run auth integration tests to verify

## Smoke Results

- **Before upgrade:** Smoke passed (2024-06-01)
- **After upgrade:** Pending

## Rollback

Revert `package.json`, `package-lock.json`, and any code changes. Re-run smoke to confirm baseline restoration.
