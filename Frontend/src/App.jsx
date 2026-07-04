import { useState } from 'react'
import './App.css'
import Navbar from './components/navbar'
import Footer from './components/footer'
import Chat from './components/Chat'
function App() {
  const [count, setCount] = useState(0)

  return (
    <>
  <Navbar />

 <main className="pt-20 pb-14 bg-gray-900">
    <div className="max-w-6xl mx-auto h-full">
      <Chat />
    </div>
  </main>

  <Footer />
</>
  )
}

export default App
