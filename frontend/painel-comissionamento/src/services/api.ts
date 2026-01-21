import axios from "axios"

export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_BASE_URL || "http://192.168.1.115:8000/api",
  timeout: 0,
})
