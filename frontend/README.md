# Cortex Web Dashboard

Web-based monitoring and management interface for the Cortex distributed operations network.

## Tech Stack

- **React 18** + **TypeScript** - UI framework and type safety
- **Vite** - Build tool and dev server
- **Ant Design** - UI component library
- **React Router** - Client-side routing
- **Axios** - HTTP client for API calls

## Prerequisites

- Node.js 20.x or later
- npm 10.x or later
- Running Cortex Monitor service (default: http://localhost:18000)
- Running Cortex Probe service (default: http://localhost:18001)

## Quick Start

1. **Install Dependencies**

```bash
npm install --legacy-peer-deps
```

> **Note**: Use `--legacy-peer-deps` to resolve compatibility issues with React 19 and some dependencies. Installation may take longer when running in WSL on Windows filesystem.

2. **Configure API Endpoints** (optional)

Edit `.env.development` to change API URLs:

```env
VITE_MONITOR_API_URL=http://localhost:18000
VITE_PROBE_API_URL=http://localhost:18001
```

3. **Start Development Server**

```bash
npm run dev
```

The dashboard will be available at http://localhost:5173

4. **Build for Production**

```bash
npm run build
```

Built files will be in the `dist/` directory.

## Project Structure

```
frontend/
├── src/
│   ├── api/          # API client and HTTP utilities
│   ├── components/   # Reusable React components
│   ├── layouts/      # Page layouts
│   ├── pages/        # Page components (Dashboard, Nodes, Alerts, etc.)
│   ├── types/        # TypeScript type definitions
│   ├── utils/        # Utility functions
│   ├── App.tsx       # Main app component with routing
│   └── main.tsx      # Entry point
├── public/           # Static assets
└── package.json
```

## Available Pages

- **Dashboard** (`/`) - Cluster overview with key metrics and recent alerts
- **Nodes** (`/nodes`) - List of all cluster nodes
- **Node Details** (`/nodes/:id`) - Detailed view of a single node
- **Alerts** (`/alerts`) - Alert center with filtering and status management
- **Settings** (`/settings`) - Application configuration

## API Integration

The dashboard communicates with:

- **Monitor API** (Port 18000):
  - Cluster topology: `GET /api/v1/cluster/topology`
  - Agents: `GET /api/v1/agents`
  - Alerts: `GET /api/v1/alerts`
  - Decisions: `GET /api/v1/decisions`
  - Submit reports: `POST /api/v1/reports`

- **Probe API** (Port 18001):
  - Health check: `GET /health`
  - Status: `GET /status`
  - Trigger inspection: `POST /execute`
  - Reports: `GET /reports`, `GET /reports/{execution_id}`
  - Schedule: `POST /schedule/pause`, `POST /schedule/resume`

**Important**: Report listing is available from Probe API only. Monitor API receives reports but doesn't provide query endpoints.

See `src/api/client.ts` for the complete API client implementation.

## Development

```bash
# Install dependencies
npm install

# Start dev server with hot reload
npm run dev

# Type checking
npm run build

# Lint code
npm run lint
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_MONITOR_API_URL` | Monitor service API URL | `http://localhost:18000` |
| `VITE_PROBE_API_URL` | Probe service API URL | `http://localhost:18001` |

## License

See root LICENSE file.
