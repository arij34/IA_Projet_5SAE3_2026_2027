import { useEffect, useState } from 'react'
import { ApiError } from '../api/client'
import { createSupervisorConnectionTicket } from '../api/challenges'
import type {
  SupervisorConnectionStatus,
  SupervisorMessage,
  SupervisorTriggerType,
} from '../types/challenges'

const SUPERVISOR_PROTOCOL = 'freelancy.supervisor.v1'
const MAX_RECONNECT_ATTEMPTS = 6
const MAX_RECONNECT_DELAY_MS = 8_000

interface SupervisorChannelState {
  attemptId: number
  messages: SupervisorMessage[]
  status: SupervisorConnectionStatus
}

function isSupervisorTriggerType(value: unknown): value is SupervisorTriggerType {
  return (
    value === 'repeated_errors' ||
    value === 'positive_feedback' ||
    value === 'slow_progress' ||
    value === 'repeated_answer_changes' ||
    value === 'long_response' ||
    value === 'multiple_timeouts'
  )
}

function parseSupervisorEvent(
  payload: unknown,
  attemptId: number,
): SupervisorMessage | null {
  if (typeof payload !== 'object' || payload === null || !('event' in payload)) {
    return null
  }

  const event = payload.event
  if (typeof event !== 'object' || event === null) return null

  const candidate = event as Record<string, unknown>
  if (
    typeof candidate.id !== 'number' ||
    !Number.isSafeInteger(candidate.id) ||
    typeof candidate.attempt_id !== 'number' ||
    candidate.attempt_id !== attemptId ||
    !isSupervisorTriggerType(candidate.trigger_type) ||
    typeof candidate.message !== 'string' ||
    candidate.message.length < 1 ||
    candidate.message.length > 240 ||
    typeof candidate.prompt_version !== 'string' ||
    typeof candidate.llm_provider !== 'string' ||
    typeof candidate.created_at !== 'string' ||
    (candidate.generation_status !== 'GENERATED' &&
      candidate.generation_status !== 'FALLBACK')
  ) {
    return null
  }

  return {
    id: candidate.id,
    attempt_id: candidate.attempt_id,
    trigger_type: candidate.trigger_type,
    message: candidate.message,
    prompt_version: candidate.prompt_version,
    generation_status: candidate.generation_status,
    llm_provider: candidate.llm_provider,
    created_at: candidate.created_at,
  }
}

export function useSupervisorChannel(attemptId: number) {
  const [channelState, setChannelState] = useState<SupervisorChannelState>(() => ({
    attemptId,
    messages: [],
    status: 'connecting',
  }))

  useEffect(() => {
    let cancelled = false
    let reconnectTimer: number | undefined
    let reconnectAttempts = 0
    let activeSocket: WebSocket | null = null
    const receivedEventIds = new Set<number>()

    const setUnavailable = () => {
      if (!cancelled) {
        setChannelState((current) => ({
          attemptId,
          messages: current.attemptId === attemptId ? current.messages : [],
          status: 'unavailable',
        }))
      }
    }

    const scheduleReconnect = () => {
      if (cancelled) return
      if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
        setUnavailable()
        return
      }

      const delay = Math.min(500 * 2 ** reconnectAttempts, MAX_RECONNECT_DELAY_MS)
      reconnectAttempts += 1
      setChannelState((current) => ({
        attemptId,
        messages: current.attemptId === attemptId ? current.messages : [],
        status: 'reconnecting',
      }))
      reconnectTimer = window.setTimeout(() => void connect(), delay)
    }

    const connect = async () => {
      try {
        const { ticket } = await createSupervisorConnectionTicket(attemptId)
        if (cancelled) return

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
        const socket = new WebSocket(
          `${protocol}//${window.location.host}/ws/challenges/attempts/${attemptId}/supervisor/`,
          [SUPERVISOR_PROTOCOL, `ticket.${ticket}`],
        )
        activeSocket = socket

        socket.onopen = () => {
          if (cancelled) return
          reconnectAttempts = 0
          setChannelState((current) => ({
            attemptId,
            messages: current.attemptId === attemptId ? current.messages : [],
            status: 'connected',
          }))
        }

        socket.onmessage = (event: MessageEvent<string>) => {
          if (cancelled) return
          let payload: unknown
          try {
            payload = JSON.parse(event.data) as unknown
          } catch {
            return
          }

          const message = parseSupervisorEvent(payload, attemptId)
          if (!message) return

          if (!receivedEventIds.has(message.id)) {
            receivedEventIds.add(message.id)
            setChannelState((current) => ({
              attemptId,
              messages: current.attemptId === attemptId
                ? [...current.messages, message]
                : [message],
              status: current.attemptId === attemptId ? current.status : 'connected',
            }))
          }
          if (socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: 'ack', event_id: message.id }))
          }
        }

        socket.onclose = (event) => {
          if (cancelled) return
          activeSocket = null
          if (event.code === 1000) {
            setChannelState((current) => ({
              attemptId,
              messages: current.attemptId === attemptId ? current.messages : [],
              status: 'idle',
            }))
          } else if ([4400, 4401, 4403].includes(event.code)) {
            setUnavailable()
          } else {
            scheduleReconnect()
          }
        }

        socket.onerror = () => socket.close()
      } catch (error: unknown) {
        if (cancelled) return
        // Non-transient failures (including 500, completed attempt 409 and
        // throttling 429) must not be retried; network errors and 502-504 are.
        if (
          error instanceof ApiError &&
          [400, 401, 403, 404, 409, 429, 500].includes(error.status)
        ) {
          setUnavailable()
          return
        }
        scheduleReconnect()
      }
    }

    void connect()

    return () => {
      cancelled = true
      if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer)
      if (
        activeSocket &&
        (activeSocket.readyState === WebSocket.CONNECTING ||
          activeSocket.readyState === WebSocket.OPEN)
      ) {
        activeSocket.close(1000)
      }
    }
  }, [attemptId])

  return channelState.attemptId === attemptId
    ? { messages: channelState.messages, status: channelState.status }
    : { messages: [], status: 'connecting' as const }
}
