import { Outlet, useLocation } from 'react-router-dom'
import Navbar from './Navbar'

export default function AppLayout() {
  const location = useLocation()
  return (
    <div className="min-h-screen bg-bg text-white flex flex-col">
      <Navbar />
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 py-6">
        <div key={location.pathname} className="animate-page-enter">
          <Outlet />
        </div>
      </main>
      <footer className="border-t border-border text-sub text-xs text-center py-4">
        UEFAgraphics · Data: FBref / Understat · Built by mykldggn
      </footer>
    </div>
  )
}
