"use client"

import { useEffect, useRef } from "react"

interface TerminalProps {
  output: string
  error: string
}

export default function Terminal({ output, error }: TerminalProps) {
  const terminalRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when output changes
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight
    }
  }, [output, error])

  return (
    <div className="h-full flex flex-col">
      <div className="p-2 bg-gray-800 text-gray-400 text-sm border-b border-gray-700">Terminal Output</div>
      <div ref={terminalRef} className="flex-1 p-4 font-mono text-sm bg-black overflow-auto whitespace-pre-wrap">
        {output && <div className="text-green-400">{output}</div>}
        {error && <div className="text-red-400">{error}</div>}
        {!output && !error && <div className="text-gray-500 italic">Run your code to see output here...</div>}
      </div>
    </div>
  )
}
