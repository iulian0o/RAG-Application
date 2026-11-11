import { useState } from "react"

export function useRequest<T>() {
  const [data, setData] = useState<T | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")

  async function run(request: () => Promise<T>) {
    setBusy(true)
    setError("")
    setData(null)

    try {
      setData(await request())
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Request failed.")
    } finally {
      setBusy(false)
    }
  }

  return { data, busy, error, run }
}