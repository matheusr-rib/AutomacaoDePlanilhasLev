"use client"

import { useMemo, useState } from "react"
import { api } from "@/services/api"
import { Banco, ExecucaoResponse } from "@/lib/types"
import { HeaderLev } from "@/components/HeaderLev"
import { UploadCard } from "@/components/UploadCard"
import { PrimaryButton } from "@/components/PrimaryButton"
import { MetricsDetails } from "@/components/MetricsDetails"
import { aguardarExecucao } from "@/lib/pollingExecucao"

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

    // 🔹 POST rápido (gera execucao_id)
    const { data } = await api.post("/execucoes/atualizacao", form)

    const execucaoId = data.execucao_id
    if (!execucaoId) {
      throw new Error("Execução não iniciada")
    }

    // 🔁 polling de status
    const statusFinal = await aguardarExecucao(execucaoId)

    if (statusFinal.status === "ERROR") {
      throw new Error(statusFinal.erro || "Erro no processamento")
    }

    // ✅ finalizou
    setResult({
      status: "success",
      execucao_id: execucaoId,
      download_url: `${process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api"}/execucoes/${execucaoId}/download`,
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

  async function baixarPlanilha(url: string) {
  try {
    const response = await fetch(url, {
      method: "GET",
    })

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

            {/* Upload Interno */}
            <UploadCard
              title="Tabela interna"
              hint="Formato XLSX (obrigatório)"
              accept=".xlsx"
              file={arquivoInterno}
              onFileChange={setArquivoInterno}
            />

            {/* Upload Banco */}
            <UploadCard
              title="Relatório do banco"
              hint="CSV, XLS ou XLSX (obrigatório)"
              accept=".csv,.xls,.xlsx"
              file={arquivoBanco}
              onFileChange={setArquivoBanco}
            />
          </div>

          {/* Botão executar */}
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

          {/* Erro */}
          {error && (
            <div className="mt-6 rounded-xl border border-red-900/50 bg-red-950/30 p-4 text-sm text-red-200">
              {error}
            </div>
          )}

          {/* Sucesso */}
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
