import { useRef, useState } from "react"

interface UploadCardProps {
  title: string
  hint: string
  accept?: string
  file: File | null
  onFileChange: (file: File | null) => void
}

export function UploadCard({
  title,
  hint,
  accept = ".xlsx,.csv,.pdf",
  file,
  onFileChange,
}: UploadCardProps) {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [dragOver, setDragOver] = useState(false)

  function openPicker() {
    inputRef.current?.click()
  }

  function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] || null
    onFileChange(f)
  }

  function onDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files?.[0] || null
    if (f) onFileChange(f)
  }

  return (
    <div
      className={[
        "rounded-xl border border-zinc-800 bg-zinc-950/40",
        "p-5",
        dragOver ? "ring-2 ring-[#F97316]/70 border-[#F97316]/70" : "",
      ].join(" ")}
      onDragOver={(e) => {
        e.preventDefault()
        setDragOver(true)
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDrop}
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold">{title}</h3>
          <p className="text-zinc-400 text-sm mt-1">{hint}</p>
        </div>

        <button
          type="button"
          onClick={openPicker}
          className="text-sm px-3 py-2 rounded-lg border border-zinc-800 hover:border-zinc-700 text-zinc-200 transition-colors"
        >
          Selecionar
        </button>
      </div>

      <div className="mt-4 rounded-lg border border-dashed border-zinc-800 p-4">
        {!file ? (
          <p className="text-zinc-400 text-sm">
            Arraste o arquivo aqui ou clique em <span className="text-white">Selecionar</span>.
          </p>
        ) : (
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="text-sm text-white truncate">{file.name}</p>
              <p className="text-xs text-zinc-400 mt-1">
                {(file.size / 1024 / 1024).toFixed(2)} MB
              </p>
            </div>
            <button
              type="button"
              onClick={() => onFileChange(null)}
              className="text-xs px-3 py-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 transition-colors"
            >
              Remover
            </button>
          </div>
        )}
      </div>

      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={onPick}
      />
    </div>
  )
}
