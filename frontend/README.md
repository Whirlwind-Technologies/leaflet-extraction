# Leaflet AI - Frontend

Next.js 15 frontend for the AI-Powered Leaflet Data Extraction Platform.

## Tech Stack

- **Framework**: Next.js 15 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Components**: shadcn/ui
- **Toasts**: Sonner
- **State**: Zustand (minimal usage, prefer server state)
- **Data Fetching**: Server Actions

## Project Structure

```
frontend/
├── app/                          # App Router pages
│   ├── (auth)/                   # Auth group (login, register)
│   │   ├── login/
│   │   └── register/
│   ├── (dashboard)/              # Dashboard group (protected)
│   │   ├── dashboard/
│   │   ├── upload/
│   │   └── leaflets/[id]/
│   ├── globals.css
│   ├── layout.tsx
│   └── page.tsx
├── components/
│   ├── auth/                     # Auth components
│   ├── dashboard/                # Dashboard components
│   ├── leaflet/                  # Leaflet-specific components
│   ├── ui/                       # shadcn/ui components
│   └── upload/                   # Upload components
├── lib/
│   ├── actions/                  # Server Actions
│   │   ├── auth.ts
│   │   └── leaflets.ts
│   ├── api-client.ts             # API utilities
│   ├── types.ts                  # TypeScript types
│   └── utils.ts                  # Utility functions
└── public/                       # Static assets
```

## Getting Started

### Prerequisites

- Node.js 20+
- npm or yarn

### Installation

```bash
# Install dependencies
npm install

# Create environment file
cp .env.local.example .env.local

# Start development server
npm run dev
```

### Environment Variables

```env
# Backend API URL (server-side)
BACKEND_URL=http://localhost:8000
```

## Development

```bash
# Start development server
npm run dev

# Build for production
npm run build

# Start production server
npm start

# Run linting
npm run lint

# Type checking
npm run type-check
```

## Key Features

### Server Actions

All API calls are made through Server Actions for:
- Type-safe data fetching
- Automatic revalidation
- Built-in error handling
- Cookie-based authentication

### Authentication

- JWT tokens stored in HTTP-only cookies
- Server-side auth checking in layouts
- Automatic redirect on auth failures

### File Upload

- Drag-and-drop support via react-dropzone
- Progress feedback during upload
- Client-side validation (file type, size)
- Server-side validation via Server Actions

## Deployment

### Docker

```bash
docker build -t leaflet-frontend .
docker run -p 3000:3000 -e BACKEND_URL=http://api:8000 leaflet-frontend
```

### Docker Compose

```bash
docker-compose up -d frontend
```

## License

MIT