import { useState } from 'react'
import './App.css'
import Navbar from './components/navbar'
import Footer from './components/footer'
import Chat from './components/Chat'
import Sidebar from './components/Sidebar'

function App() {
  const [showSidebar, setShowSidebar] = useState(true)
  
  return (
    <>
      <Navbar onToggleSidebar={() => setShowSidebar((open) => !open)} sidebarOpen={showSidebar} />

      <main className="pt-20 pb-9 bg-gray-900 px-2 h-screen overflow-hidden">
        <div className={`w-full px-3 h-full overflow-hidden flex items-stretch ${showSidebar ? 'gap-4' : 'gap-0'}`}>
          <Sidebar isOpen={showSidebar} />
          <div className="flex-1 flex justify-center">
            <Chat />
          </div>
        </div>
      </main>

      <Footer />
    </>
  )
}

export default App
