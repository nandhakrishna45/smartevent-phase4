import React, { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
function App() {
  const [token, setToken] = useState(sessionStorage.getItem('token') || '')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [events, setEvents] = useState([])
  const [wishlist, setWishlist] = useState([])
  const [recommendations, setRecommendations] = useState([])
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [location, setLocation] = useState('')
  const [sortBy, setSortBy] = useState('date')
  const [chatText, setChatText] = useState('')
  const [chatReply, setChatReply] = useState('')
  const [notice, setNotice] = useState('')

  async function request(path, options = {}) {
    const response = await fetch(`${API}${path}`, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(options.headers || {}) }
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(data.detail || 'Request failed')
    return data
  }
  async function login(e) {
    e.preventDefault()
    try {
      const body = new URLSearchParams({ username: email, password })
      const response = await fetch(`${API}/auth/login`, { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Login failed')
      sessionStorage.setItem('token', data.access_token); setToken(data.access_token); setNotice('Signed in successfully')
    } catch (err) { setNotice(err.message) }
  }
  async function loadEvents() {
    try {
      const params = new URLSearchParams()
      if (query) params.set('q', query)
      if (category) params.set('category', category)
      if (location) params.set('location', location)
      params.set('sort_by', sortBy)
      setEvents(await request(`/events?${params.toString()}`))
    } catch (err) { setNotice(err.message) }
  }
  async function loadPersonal() {
    if (!token) return
    try {
      const [w, r] = await Promise.all([request('/wishlist'), request('/recommendations')])
      setWishlist(w); setRecommendations(r.recommended_for_you || [])
    } catch (err) { setNotice(err.message) }
  }
  useEffect(() => { loadEvents() }, [])
  useEffect(() => { loadPersonal() }, [token])
  useEffect(() => {
    const sockets = events.map(event => {
      const ws = new WebSocket(`${API.replace(/^http/, 'ws')}/ws/events/${event.id}/availability`)
      ws.onmessage = e => {
        const update = JSON.parse(e.data)
        setEvents(prev => prev.map(item => item.id === update.event_id ? { ...item, available_tickets: update.available_tickets } : item))
      }
      return ws
    })
    return () => sockets.forEach(ws => ws.close())
  }, [events.length])
  async function saveEvent(id) {
    try { await request(`/wishlist/${id}`, { method: 'POST' }); await loadPersonal(); setNotice('Event saved') }
    catch (err) { setNotice(err.message) }
  }
  async function bookEvent(id) {
    try { const data = await request(`/events/${id}/book`, { method: 'POST' }); setNotice(`Booking confirmed: #${data.booking_id}`); await loadEvents() }
    catch (err) { setNotice(err.message) }
  }
  async function sendChat(e) {
    e.preventDefault()
    try { const data = await request('/chat', { method: 'POST', body: JSON.stringify({ message: chatText }) }); setChatReply(data.reply + (data.events?.length ? '\\n' + data.events.map(x => x.title).join('\\n') : '')); }
    catch (err) { setChatReply(err.message) }
  }
  return <main className="shell">
    <header><div><p className="eyebrow">SMART EVENT PLATFORM</p><h1>Discover something worth going to.</h1><p className="muted">Phase 4 · Real-time experience, personalization & AI</p></div>
      <div className="login">{token ? <button className="secondary" onClick={() => { sessionStorage.removeItem('token'); setToken(''); setNotice('Signed out') }}>Sign out</button> :
      <form onSubmit={login}><input aria-label="Email" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} required/><input aria-label="Password" type="password" placeholder="Password" value={password} onChange={e => setPassword(e.target.value)} required/><button>Sign in</button><small>Register via POST /auth/register in API docs.</small></form>}</div>
    </header>
    {notice && <p className="notice">{notice}</p>}
    <section className="filters"><input placeholder="Search events" value={query} onChange={e => setQuery(e.target.value)}/><input placeholder="Category" value={category} onChange={e => setCategory(e.target.value)}/><input placeholder="Location" value={location} onChange={e => setLocation(e.target.value)}/><select value={sortBy} onChange={e => setSortBy(e.target.value)}><option value="date">Date</option><option value="price">Price</option><option value="popularity">Popularity</option></select><button onClick={loadEvents}>Search</button></section>
    <section><div className="section-head"><h2>Explore events</h2><span>{events.length} results</span></div><div className="grid">{events.map(event => <article className="event" key={event.id}><span className="tag">{event.category}</span><h3>{event.title}</h3><p>{event.description || 'An event to add to your calendar.'}</p><p className="muted">{event.location} · {new Date(event.event_date).toLocaleString()}</p><div className="event-bottom"><strong>₹{event.price}</strong><span>{event.available_tickets} tickets left</span></div><div className="actions"><button disabled={!token || event.available_tickets < 1} onClick={() => bookEvent(event.id)}>{event.available_tickets < 1 ? 'Sold out' : 'Book tickets'}</button><button className="secondary" disabled={!token} onClick={() => saveEvent(event.id)}>♡ Save</button></div></article>)}</div></section>
    {token && <section><div className="section-head"><h2>Recommended for you</h2><span>Based on your profile and event popularity</span></div><div className="chips">{recommendations.map(e => <span key={e.id}>{e.title} · ₹{e.price}</span>)}</div><h2 className="subhead">Your wishlist</h2><div className="chips">{wishlist.map(w => <span key={w.id}>{w.event.title}</span>)}{!wishlist.length && <p className="muted">Save an event to see it here.</p>}</div></section>}
    <section className="assistant"><div><p className="eyebrow">SMART ASSISTANT</p><h2>What can I help you find?</h2><p className="muted">Try “trending events”, “music events near me”, or “show my bookings”.</p></div><form onSubmit={sendChat}><input placeholder="Ask SmartEvent…" value={chatText} onChange={e => setChatText(e.target.value)} required/><button disabled={!token}>Ask</button></form>{chatReply && <pre>{chatReply}</pre>}</section>
    <footer>SmartEvent · Phase 4 starter repository</footer>
  </main>
}
createRoot(document.getElementById('root')).render(<App />)
