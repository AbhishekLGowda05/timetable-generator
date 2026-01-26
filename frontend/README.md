# Timetable Generator Frontend

A production-ready React frontend for generating optimized school timetables using a constraint-based solver.

## Features

- **Step-by-Step Wizard**: Upload → Configure Constraints → Generate → View Results
- **Interactive Timetable Grid**: View schedules by class, teacher, or resource
- **Real-time Job Tracking**: Live progress updates with WebSocket-like polling
- **Export Options**: Download timetables as Excel, CSV, PDF, or JSON
- **Soft/Hard Constraint Configuration**: Balance between hard rules and soft preferences
- **Teacher & Class Overrides**: Fine-tune individual availability and constraints
- **Recent Jobs History**: Quick access to past generation results

## Tech Stack

- **React 18** with TypeScript
- **Vite** for fast development and optimized builds
- **TailwindCSS** with **shadcn/ui** components
- **TanStack Query** for server state management
- **Zustand** for client state management
- **react-hook-form** with **Zod** validation
- **MSW** for API mocking in development

## Getting Started

### Prerequisites

- Node.js 18+ 
- npm or pnpm

### Installation

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The app will be available at `http://localhost:5173`

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# API base URL (proxied through Vite in development)
VITE_API_BASE_URL=http://localhost:8010

# Enable mock API for standalone development
VITE_USE_MOCK_API=true
```

### Development with Mock API

To run the frontend without a backend:

```bash
# Set mock mode
echo "VITE_USE_MOCK_API=true" >> .env

# Start dev server
npm run dev
```

The mock server provides realistic responses including:
- File upload handling
- Job creation and progress simulation
- Mock timetable results
- All CRUD operations

### Development with Real Backend

Ensure the backend server is running on port 8010:

```bash
# In the server directory
cd ../server
pip install -r requirements.txt
python -m app.main

# In the frontend directory
VITE_USE_MOCK_API=false npm run dev
```

## Project Structure

```
frontend/
├── public/
│   └── demo-data.json       # Sample data for testing
├── src/
│   ├── components/
│   │   ├── ui/              # shadcn/ui components
│   │   └── TimetableGrid.tsx # Reusable timetable component
│   ├── layouts/
│   │   └── AppLayout.tsx    # Main layout with sidebar
│   ├── lib/
│   │   ├── api.ts           # API functions
│   │   ├── api-client.ts    # Axios client configuration
│   │   ├── schemas.ts       # Zod validation schemas
│   │   └── utils.ts         # Utility functions
│   ├── mocks/
│   │   ├── handlers.ts      # MSW request handlers
│   │   └── browser.ts       # MSW browser setup
│   ├── pages/
│   │   ├── LandingPage.tsx
│   │   ├── UploadPage.tsx
│   │   ├── ConstraintsPage.tsx
│   │   ├── GeneratePage.tsx
│   │   ├── ResultsPage.tsx
│   │   └── RecentJobsPage.tsx
│   ├── stores/
│   │   └── index.ts         # Zustand stores
│   ├── App.tsx              # Route definitions
│   └── main.tsx             # Entry point
├── package.json
├── tailwind.config.js
├── tsconfig.json
└── vite.config.ts
```

## Available Scripts

| Script | Description |
|--------|-------------|
| `npm run dev` | Start development server |
| `npm run build` | Build for production |
| `npm run preview` | Preview production build |
| `npm run lint` | Run ESLint |
| `npm run lint:fix` | Fix ESLint errors |
| `npm run format` | Format with Prettier |
| `npm run test` | Run unit tests |
| `npm run test:watch` | Run tests in watch mode |
| `npm run test:coverage` | Run tests with coverage |
| `npm run test:e2e` | Run Playwright E2E tests |
| `npm run storybook` | Start Storybook |
| `npm run type-check` | TypeScript type checking |

## API Endpoints

The frontend communicates with the following API endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/upload` | Upload school data file |
| POST | `/api/upload/bulk` | Upload all-in-one Excel file |
| POST | `/api/validate` | Validate solver input |
| POST | `/api/solve` | Create a new solve job |
| GET | `/api/status/:id` | Get job status |
| GET | `/api/result/:id` | Get job result |
| POST | `/api/cancel/:id` | Cancel a job |
| POST | `/api/rerun/:id` | Rerun a job with new params |
| GET | `/api/jobs` | List all jobs |

## Workflow

1. **Upload Data**: Upload Excel/CSV files or use sample data
2. **Configure Constraints**: 
   - Toggle hard constraints (must be satisfied)
   - Adjust soft constraint weights
   - Set teacher/class-specific overrides
3. **Generate**: Submit to solver and monitor progress
4. **View Results**: 
   - Browse by class, teacher, or resource view
   - Check soft constraint violations
   - Export in various formats

## Styling Guide

The UI follows the Acadion AI / SchoolOS design system:
- Clean white canvas with subtle borders
- Blue primary color (`#2563eb`)
- Card-based layouts with consistent spacing
- Left sidebar navigation
- Responsive design (mobile-friendly)

CSS variables are defined in `src/index.css` for theme customization.

## Testing

### Unit Tests

```bash
# Run once
npm run test

# Watch mode
npm run test:watch

# With coverage
npm run test:coverage
```

### E2E Tests

```bash
# Run headless
npm run test:e2e

# Interactive UI
npm run test:e2e:ui
```

### Storybook

```bash
# Start Storybook
npm run storybook
```

## Building for Production

```bash
# Build
npm run build

# Preview build locally
npm run preview
```

The build output will be in the `dist/` directory.

## Integration with SchoolOS

This frontend is designed to be easily integrated into the main SchoolOS/Acadion AI application:

1. Copy the `src/` directory to the target project
2. Merge dependencies from `package.json`
3. Import and mount routes from `App.tsx`
4. Ensure API proxy configuration matches

## Contributing

1. Follow the existing code style
2. Write tests for new features
3. Update Storybook stories for new components
4. Ensure all lints pass before submitting PRs

## License

MIT
