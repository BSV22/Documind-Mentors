import React from 'react'

const navbar = () => {
    return (
       <div className="fixed top-0 left-0 w-full z-50 px-4 py-2">
  <nav className="bg-gray-800 rounded-2xl px-6 py-3">
    <div className="flex items-center justify-between">
      <h1 className="text-white font-bold text-xl cursor-pointer">
        Documind
      </h1>

      <ul className="flex items-center gap-8 text-white">
        <li className="cursor-pointer hover:text-gray-300">Home</li>
        <li className="cursor-pointer hover:text-gray-300">About</li>
        <li className="cursor-pointer hover:text-gray-300">Contact</li>
      </ul>
    </div>
  </nav>
</div>
    )
}

export default navbar
