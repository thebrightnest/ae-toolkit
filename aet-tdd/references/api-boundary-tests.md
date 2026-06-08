# API Boundary Tests

An API boundary test validates the contract between a backend endpoint and its frontend consumer without running a full E2E stack.

## When Required

When a vertical slice introduces **both** a backend route and frontend code that calls it, an API boundary test is mandatory before `tdd-complete`.

## What It Is (and Is Not)

- **Is:** A test that exercises the HTTP contract — request shape, response shape, status codes, and error handling — with the backend or HTTP layer mocked.
- **Is not:** An E2E test. It does not spin up a real browser or full server.

## Examples by Stack

### Laravel Backend

Use `Http::fake()` to assert the frontend receives the expected payload shape:

```php
Http::fake(['api/v1/orders/*' => Http::response(['status' => 'pending'])]);

$response = $this->get('/orders/1');
$response->assertOk();
$response->assertJsonPath('status', 'pending');
```

### React Frontend

Use MSW or a stubbed fetch to assert the component handles the contract:

```typescript
import { rest } from 'msw';
import { server } from './mocks/server';

server.use(
  rest.get('/api/v1/orders/1', (req, res, ctx) =>
    res(ctx.json({ status: 'pending' }))
  )
);

render(<OrderDetail orderId={1} />);
expect(await screen.findByText('pending')).toBeInTheDocument();
```

Or with a minimal stub:

```typescript
global.fetch = vi.fn(() =>
  Promise.resolve({ json: () => Promise.resolve({ status: "pending" }) }),
);
```

## Checklist

- [ ] Request URL, method, and payload shape match the backend contract
- [ ] Response is consumed through the same abstraction the production code uses
- [ ] Error status codes (4xx, 5xx) have explicit test coverage
