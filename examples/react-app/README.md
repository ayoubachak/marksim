# Market Simulation - React TypeScript UI

A modern React + TypeScript application for visualizing and controlling market simulation agents in real-time.

## 🚀 Features

- ✅ **TypeScript** - Full type safety throughout
- ✅ **shadcn/ui** - Beautiful, accessible components
- ✅ **Real-time WebSocket** - Live market data streaming
- ✅ **Dark Mode** - Toggle between light and dark themes
- ✅ **Order Book Visualization** - See bids and asks with color coding
- ✅ **Agent Monitoring** - Watch agent configurations update in real-time
- ✅ **Market Statistics** - Price, spread, volume, trade count

## 📦 Project Structure

```
src/
├── components/
│   └── ui/              # shadcn/ui components
│       ├── button.tsx
│       └── card.tsx
├── hooks/
│   └── useWebSocket.ts  # WebSocket connection hook
├── lib/
│   └── utils.ts         # Utility functions
├── types/
│   └── index.ts         # TypeScript type definitions
├── App.tsx              # Main application
└── main.tsx             # Entry point
```

## 🏃 Getting Started

### 1. Install Dependencies
```bash
npm install
```

### 2. Start Development Server
```bash
npm run dev
```

### 3. Start Market Simulation
In another terminal:
```bash
python -m marksim.main
```

### 4. Open Browser
Navigate to `http://localhost:5173` (or the port shown by Vite)

## 🎨 Components Created

### Core Components
- `Button` - Styled button component with variants
- `Card` - Container component for sections
- `useWebSocket` - Custom hook for WebSocket management

### Features
- Real-time market data updates
- Order book visualization
- Agent configuration display
- Statistics dashboard
- Dark mode toggle

## 🎯 Next Steps

- [ ] Add KlineCharts for candlestick visualization
- [ ] Create agent control panel (sliders/inputs)
- [ ] Add chart timeframe switching
- [ ] Implement volume analytics
- [ ] Add trade history
- [ ] Create agent parameter modification UI

## 🛠️ Development

### Build for Production
```bash
npm run build
```

### Preview Production Build
```bash
npm run preview
```

### Lint
```bash
npm run lint
```

## 📝 Notes

The app uses:
- **React 19** with TypeScript
- **Vite** for fast development
- **Tailwind CSS** v4 for styling
- **shadcn/ui** for components
- **lucide-react** for icons

All WebSocket message types are strongly typed for safety!
