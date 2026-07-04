import { useState } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from './assets/vite.svg'
import heroImg from './assets/hero.png'
import './App.css'
import Navbar from './components/navbar'
import Footer from './components/footer'
function App() {
  const [count, setCount] = useState(0)

  return (
   <>
  <Navbar />

  <main className="min-h-lvh bg-gray-900 flex items-center justify-center px-4">
    <div className="w-full max-w-4xl">
      <div className="flex items-center gap-3 bg-gray-700 p-3 rounded-2xl">
        <input
          type="text"
          placeholder="Ask..."
          className="flex-1 bg-transparent text-white placeholder-gray-400 outline-none px-3 py-2"
        />

        <button className="bg-blue-600 hover:bg-blue-700 text-white px-5 py-2 rounded-xl">
          Send
        </button>
      </div>
    </div>
  </main>
  <Footer />
</>
  )
}

export default App
