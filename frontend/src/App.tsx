import { Routes, Route } from 'react-router-dom'
import AppLayout from './components/layout/AppLayout'
import HomePage from './pages/HomePage'
import PlayerPage from './pages/PlayerPage'
import TeamPage from './pages/TeamPage'
import LeaguePage from './pages/LeaguePage'

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/player/:playerId" element={<PlayerPage />} />
        <Route path="/team/:teamId" element={<TeamPage />} />
        <Route path="/league/:leagueId" element={<LeaguePage />} />
      </Route>
    </Routes>
  )
}
