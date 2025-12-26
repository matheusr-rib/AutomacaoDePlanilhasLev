import { ExecucaoResponse } from "@/lib/types"

export function MetricsDetails({ data }: { data: ExecucaoResponse }) {
  if (!data.acoes || !data.cache || !data.padronizacao) return null

  const abrir = data.acoes.abrir ?? 0
  const fechar = data.acoes.fechar ?? 0
  const atualizar = data.acoes.atualizar ?? 0
  const novas = data.cache.novas ?? 0
  const chamadasIA = data.padronizacao.chamadas_ia ?? 0

  return (
    <details className="mt-6 rounded-xl border border-zinc-800 bg-zinc-950/40 p-5">
      <summary className="cursor-pointer select-none text-sm text-zinc-200">
        Ver detalhes (métricas)
      </summary>

      <div className="grid grid-cols-1 sm:grid-cols-5 gap-3 mt-4">
        <Metric label="Ações ABRIR" value={abrir} />
        <Metric label="Ações FECHAR" value={fechar} />
        <Metric label="Ações ATUALIZAR" value={atualizar} />
        <Metric label="Novas chaves" value={novas} />
        <Metric label="Chamadas IA" value={chamadasIA} />
      </div>
    </details>
  )
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
      <p className="text-xs text-zinc-400">{label}</p>
      <p className="text-2xl font-semibold mt-1">{value}</p>
    </div>
  )
}
