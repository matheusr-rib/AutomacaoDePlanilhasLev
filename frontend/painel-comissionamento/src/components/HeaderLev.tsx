import Image from "next/image"

export function HeaderLev() {
  return (
    <header className="flex items-center justify-between mb-8">
      <div className="flex items-center gap-4">
        <div className="relative w-14 h-14">
          <Image
            src="/lev-logo.png"
            alt="Lev Negócios"
            fill
            className="object-contain"
            priority
          />
        </div>

        <div>
          <h1 className="text-3xl font-semibold tracking-tight">
            Atualização de planilhas de comissionamento
          </h1>
          <p className="text-zinc-400 mt-1">
            
        • Lev Negócios
          </p>
        </div>
      </div>

      <span className="text-xs px-3 py-1 rounded-full border border-zinc-800 text-zinc-300">
        Sistema operacional
      </span>
    </header>
  )
}
