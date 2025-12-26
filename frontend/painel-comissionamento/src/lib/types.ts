export type Banco = "HOPE"

export interface ExecucaoResponse {
  status: "success" | "error"
  execucao_id?: string
  download_url?: string
  resumo?: {
    linhas_banco: number
    linhas_interno: number
    linhas_saida: number
  }
  acoes?: {
    abrir: number
    fechar: number
    atualizar: number
  }
  cache?: {
    inicial: number
    novas: number
    final: number
  }
  padronizacao?: {
    consultas_cache?: number
    hits_cache?: number
    chamadas_ia?: number
    linhas_csv?: number
  }
  erro?: string
}
