export class ApiError extends Error {
  status: number | null
  traceId: string | null

  constructor(message: string, status: number | null = null, traceId: string | null = null) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.traceId = traceId
  }
}

export function traceIdFrom(response: Response): string | null {
  const value = response.headers.get("X-Trace-Id")
  return value && value.trim() ? value.trim() : null
}