"use client";

import { useState, useRef, useEffect } from "react";
import CodeEditor from "@/components/code-editor";
import Terminal from "@/components/terminal";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";

export default function Home() {
  const [code, setCode] = useState('print("Hello, world!")');
  const [output, setOutput] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const codeRef = useRef(code);

  // Update the ref whenever code changes
  useEffect(() => {
    codeRef.current = code;
  }, [code]);

  const runCode = async () => {
    setIsLoading(true);
    setOutput("");
    setError("");

    try {
      const response = await fetch("http://localhost:8000/api/execute", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ code: codeRef.current }),
      });

      const data = await response.json();

      if (data.exit_code === 0) {
        setOutput(data.output);
      } else {
        setError(data.error);
      }
    } catch (err: any) {
      setError(`Failed to connect to API: ${err?.message || "Unknown error"}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="flex flex-col h-screen bg-gray-900 text-white">
      <header className="p-4 border-b border-gray-700 flex justify-between items-center">
        <h1 className="text-xl font-bold">Python Code Editor</h1>
        <Button
          onClick={runCode}
          disabled={isLoading}
          className="bg-green-600 hover:bg-green-700"
        >
          {isLoading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Running...
            </>
          ) : (
            "Run Code"
          )}
        </Button>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <div className="w-1/2 border-r border-gray-700">
          <CodeEditor code={code} onChange={setCode} onExecute={runCode} />
        </div>
        <div className="w-1/2">
          <Terminal output={output} error={error} />
        </div>
      </div>
    </main>
  );
}
