import { api } from "@/services/api"

export interface StatusExecucao {
  status: "PROCESSING" | "DONE" | "ERROR"
  erro?: string
  resultado?: any
}

export async function aguardarExecucao(
  execucaoId: string,
  intervaloMs = 2000
): Promise<StatusExecucao> {
  while (true) {
    const { data } = await api.get<StatusExecucao>(
      `/execucoes/${execucaoId}/status`
    )

    if (data.status === "DONE" || data.status === "ERROR") {
      return data
    }

    await new Promise((resolve) => setTimeout(resolve, intervaloMs))
  }
}
