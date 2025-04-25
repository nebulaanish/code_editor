"use client";

import { useRef, useEffect } from "react";
import Editor, { Monaco } from "@monaco-editor/react";
import type { editor, languages } from "monaco-editor";

interface CodeEditorProps {
  code: string;
  onChange: (code: string) => void;
  onExecute?: () => void;
}

export default function CodeEditor({
  code,
  onChange,
  onExecute,
}: CodeEditorProps) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);

  const handleEditorDidMount = (
    editor: editor.IStandaloneCodeEditor,
    monaco: Monaco
  ) => {
    editorRef.current = editor;

    // Add Ctrl+Enter shortcut for code execution
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => {
      if (onExecute && editorRef.current) {
        // Get the latest code value from the editor
        const currentCode = editorRef.current.getValue();
        // Update the parent's state and wait for it to complete
        onChange(currentCode);
        // Use setTimeout to ensure state update is processed
        setTimeout(() => {
          onExecute();
        }, 0);
      }
    });

    // Configure editor settings
    editor.updateOptions({
      minimap: { enabled: false },
      fontSize: 14,
      lineNumbers: "on",
      roundedSelection: false,
      scrollBeyondLastLine: false,
      automaticLayout: true,
      tabSize: 4,
      insertSpaces: true,
      autoClosingBrackets: "always",
      autoClosingQuotes: "always",
      formatOnPaste: true,
      formatOnType: true,
      suggestOnTriggerCharacters: true,
      acceptSuggestionOnEnter: "on",
      tabCompletion: "on",
      wordBasedSuggestions: "currentDocument",
      parameterHints: { enabled: true },
    });

    // Configure Python language features
    monaco.languages.registerCompletionItemProvider("python", {
      provideCompletionItems: (model, position) => {
        const word = model.getWordUntilPosition(position);
        const range = {
          startLineNumber: position.lineNumber,
          endLineNumber: position.lineNumber,
          startColumn: word.startColumn,
          endColumn: word.endColumn,
        };

        // Add basic Python suggestions
        const suggestions: languages.CompletionItem[] = [
          {
            label: "print",
            kind: monaco.languages.CompletionItemKind.Function,
            insertText: "print(${1:message})",
            insertTextRules:
              monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
            documentation: "Print a message to the console",
            range,
          },
          {
            label: "def",
            kind: monaco.languages.CompletionItemKind.Keyword,
            insertText: "def ${1:function_name}(${2:parameters}):\n\t${3:pass}",
            insertTextRules:
              monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
            documentation: "Define a new function",
            range,
          },
          {
            label: "if",
            kind: monaco.languages.CompletionItemKind.Keyword,
            insertText: "if ${1:condition}:\n\t${2:pass}",
            insertTextRules:
              monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
            documentation: "Create an if statement",
            range,
          },
          {
            label: "for",
            kind: monaco.languages.CompletionItemKind.Keyword,
            insertText: "for ${1:item} in ${2:iterable}:\n\t${3:pass}",
            insertTextRules:
              monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
            documentation: "Create a for loop",
            range,
          },
          {
            label: "while",
            kind: monaco.languages.CompletionItemKind.Keyword,
            insertText: "while ${1:condition}:\n\t${2:pass}",
            insertTextRules:
              monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
            documentation: "Create a while loop",
            range,
          },
        ];

        return { suggestions };
      },
    });
  };

  return (
    <div className="h-full flex flex-col">
      <div className="p-2 bg-gray-800 text-gray-400 text-sm border-b border-gray-700">
        Python Editor (Ctrl+Enter to run)
      </div>
      <div className="flex-1">
        <Editor
          height="100%"
          defaultLanguage="python"
          value={code}
          onChange={(value) => onChange(value || "")}
          onMount={handleEditorDidMount}
          theme="vs-dark"
          options={{
            automaticLayout: true,
            minimap: { enabled: false },
          }}
        />
      </div>
    </div>
  );
}
