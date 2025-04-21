"use client"

import type React from "react"

import { useEffect, useRef } from "react"

interface CodeEditorProps {
  code: string
  onChange: (code: string) => void
}

export default function CodeEditor({ code, onChange }: CodeEditorProps) {
  const editorRef = useRef<HTMLTextAreaElement>(null)

  // Handle tab key to insert spaces instead of changing focus
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Tab") {
      e.preventDefault()
      const start = e.currentTarget.selectionStart
      const end = e.currentTarget.selectionEnd

      // Insert 2 spaces at cursor position
      const newValue = code.substring(0, start) + "  " + code.substring(end)
      onChange(newValue)

      // Move cursor after the inserted spaces
      setTimeout(() => {
        if (editorRef.current) {
          editorRef.current.selectionStart = start + 2
          editorRef.current.selectionEnd = start + 2
        }
      }, 0)
    }
  }

  // Auto-resize the textarea to fit content
  useEffect(() => {
    if (editorRef.current) {
      editorRef.current.style.height = "auto"
      editorRef.current.style.height = `${editorRef.current.scrollHeight}px`
    }
  }, [code])

  return (
    <div className="h-full flex flex-col">
      <div className="p-2 bg-gray-800 text-gray-400 text-sm border-b border-gray-700">Python</div>
      <textarea
        ref={editorRef}
        value={code}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        className="flex-1 w-full p-4 bg-gray-900 text-white font-mono resize-none outline-none"
        spellCheck={false}
        placeholder="Write your Python code here..."
      />
    </div>
  )
}
