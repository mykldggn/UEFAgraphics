import { Outlet, useLocation } from 'react-router-dom'
import Navbar from './Navbar'
import ScoresTicker from './ScoresTicker'

export default function AppLayout() {
  const location = useLocation()
  return (
    <div style={{ minHeight: '100vh', background: '#06080f', color: '#e6e9f4', display: 'flex', flexDirection: 'column' }}>
      <Navbar />
      <ScoresTicker />
      <main style={{ flex: 1, maxWidth: 1152, width: '100%', margin: '0 auto', padding: '24px 16px' }}>
        <div key={location.pathname} className="animate-page-enter">
          <Outlet />
        </div>
      </main>
      <footer style={{
        borderTop: '1px solid #1a2235',
        color: '#4d5e7a',
        fontSize: 11,
        textAlign: 'center',
        padding: '14px 16px',
        fontFamily: 'Inter, sans-serif',
      }}>
        UEFAgraphics · Data: FBref / Understat · Built by mykldggn
      </footer>
    </div>
  )
}
