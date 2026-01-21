"use client"

import { useMemo, useState } from "react"
import { api } from "@/services/api"
import { Banco, ExecucaoResponse } from "@/lib/types"
import { HeaderLev } from "@/components/HeaderLev"
import { UploadCard } from "@/components/UploadCard"
import { PrimaryButton } from "@/components/PrimaryButton"
import { MetricsDetails } from "@/components/MetricsDetails"
import { aguardarExecucao } from "@/lib/pollingExecucao"

// Base da API (deve apontar para o backend na rede)
// Ex: http://192.168.1.115:8000/api
const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "") || "http://192.168.1.115:8000/api"

function resolveApiUrl(pathOrUrl: string): string {
  // Se já for absoluta, retorna como está
  if (/^https?:\/\//i.test(pathOrUrl)) return pathOrUrl

  // Garante que path começa com "/"
  const path = pathOrUrl.startsWith("/") ? pathOrUrl : `/${pathOrUrl}`

  // Se backend devolver "/api/...", mantemos o host do API_BASE e encaixamos o path
  // Ex: API_BASE = http://192.168.1.115:8000/api
  // path = /api/execucoes/.../download
  // final = http://192.168.1.115:8000/api/execucoes/.../download
  const apiOrigin = API_BASE.replace(/\/api$/i, "") // http://192.168.1.115:8000
  return `${apiOrigin}${path}`
}

export default function Home() {
  const [banco, setBanco] = useState<Banco>("HOPE")
  const [arquivoInterno, setArquivoInterno] = useState<File | null>(null)
  const [arquivoBanco, setArquivoBanco] = useState<File | null>(null)

  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ExecucaoResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const canSubmit = useMemo(() => {
    return !!banco && !!arquivoInterno && !!arquivoBanco && !loading
  }, [banco, arquivoInterno, arquivoBanco, loading])

  async function executar() {
    if (!canSubmit) return

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const form = new FormData()
      form.append("banco", banco)
      form.append("arquivo_interno", arquivoInterno as File)
      form.append("arquivo_banco", arquivoBanco as File)

      // POST rápido (gera execucao_id e URLs relativas)
      const { data } = await api.post("/execucoes/atualizacao", form)

      const execucaoId = data.execucao_id
      if (!execucaoId) throw new Error("Execução não iniciada")

      // polling de status
      const statusFinal = await aguardarExecucao(execucaoId)

      if (statusFinal.status === "ERROR") {
        throw new Error(statusFinal.erro || "Erro no processamento")
      }

      // download_url agora pode vir relativo do backend (preferir isso)
      const downloadUrlRelativa: string =
        data.download_url || `/api/execucoes/${execucaoId}/download`

      setResult({
        status: "success",
        execucao_id: execucaoId,
        download_url: downloadUrlRelativa, // mantém relativo; resolve na hora de baixar
        resumo: statusFinal.resultado,
        acoes: statusFinal.resultado?.acoes,
        cache: statusFinal.resultado?.cache,
        padronizacao: statusFinal.resultado?.padronizacao,
      })
    } catch (err: unknown) {
      setError((err as Error).message || "Falha na execução")
    } finally {
      setLoading(false)
    }
  }

  async function baixarPlanilha(urlRelativaOuAbsoluta: string) {
    try {
      const url = resolveApiUrl(urlRelativaOuAbsoluta)

      const response = await fetch(url, { method: "GET" })

      if (!response.ok) {
        throw new Error(`Falha no download (${response.status})`)
      }

      const blob = await response.blob()
      const objectUrl = window.URL.createObjectURL(blob)

      const a = document.createElement("a")
      a.href = objectUrl
      a.download = "planilha_atualizacao.xlsx"
      document.body.appendChild(a)
      a.click()

      a.remove()
      window.URL.revokeObjectURL(objectUrl)
    } catch (err) {
      console.error(err)
      alert("Não foi possível baixar a planilha.")
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-black via-zinc-950 to-[#2b1248]">
      <div className="max-w-6xl mx-auto px-6 py-10">
        <HeaderLev />

        <section className="rounded-2xl border border-zinc-800 bg-zinc-950/40 p-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Banco */}
            <div className="rounded-xl border border-zinc-800 bg-zinc-950/40 p-5">
              <p className="text-xs text-zinc-400">Instituição financeira</p>
              <select
                value={banco}
                onChange={(e) => setBanco(e.target.value as Banco)}
                className="mt-2 w-full rounded-lg bg-zinc-950 border border-zinc-800 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[#F97316]/60"
              >
                <option value="HOPE">HOPE</option>
              </select>
            </div>

            <UploadCard
              title="Tabela interna"
              hint="Formato XLSX (obrigatório)"
              accept=".xlsx"
              file={arquivoInterno}
              onFileChange={setArquivoInterno}
            />

            <UploadCard
              title="Relatório do banco"
              hint="CSV, XLS ou XLSX (obrigatório)"
              accept=".csv,.xls,.xlsx"
              file={arquivoBanco}
              onFileChange={setArquivoBanco}
            />
          </div>

          <div className="mt-6">
            <PrimaryButton
              label="Executar atualização"
              loading={loading}
              disabled={!canSubmit}
              onClick={executar}
            />
            {!canSubmit && (
              <p className="text-xs text-zinc-500 mt-2">
                Selecione o banco e envie os dois arquivos para habilitar a execução.
              </p>
            )}
          </div>

          {error && (
            <div className="mt-6 rounded-xl border border-red-900/50 bg-red-950/30 p-4 text-sm text-red-200">
              {error}
            </div>
          )}

          {result?.status === "success" && (
            <>
              <MetricsDetails data={result} />

              <div className="mt-6 flex items-center justify-between gap-4 flex-wrap">
                <div className="text-sm text-zinc-300">
                  Execução concluída
                  {result.resumo?.linhas_saida != null && (
                    <span className="text-zinc-500">
                      {" "}
                      ({result.resumo.linhas_saida} linhas na atualização)
                    </span>
                  )}
                </div>

                {result.download_url && (
                  <button
                    onClick={() => baixarPlanilha(result.download_url as string)}
                    className="inline-flex items-center justify-center rounded-lg px-4 py-2 border border-zinc-800 bg-zinc-950 hover:bg-zinc-900 transition-colors text-sm"
                  >
                    Baixar planilha de atualização
                  </button>
                )}
              </div>
            </>
          )}
        </section>

        <footer className="mt-8 text-xs text-zinc-500">
          Lev Negócios • Painel interno
        </footer>
      </div>
    </div>
  )
}
