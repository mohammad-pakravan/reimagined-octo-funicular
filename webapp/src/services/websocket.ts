const API_WS_URL = import.meta.env.VITE_API_WS_URL || 'ws://localhost:8000'

export interface SignalingMessage {
  type: 'offer' | 'answer' | 'ice-candidate' | 'user-joined' | 'user-left' | 'call-ended'
  sdp?: RTCSessionDescriptionInit
  candidate?: RTCIceCandidateInit
  user_id?: number
}

export class SignalingClient {
  private ws: WebSocket | null = null
  private roomId: string
  private token: string
  private onMessage: (message: SignalingMessage) => void
  private onError: (error: Event) => void
  private onClose: () => void

  constructor(
    roomId: string,
    token: string,
    onMessage: (message: SignalingMessage) => void,
    onError: (error: Event) => void,
    onClose: () => void
  ) {
    this.roomId = roomId
    this.token = token
    this.onMessage = onMessage
    this.onError = onError
    this.onClose = onClose
  }

  connect(): void {
    const wsUrl = `${API_WS_URL.replace('http://', 'ws://').replace('https://', 'wss://')}/ws/video-call/${this.roomId}?token=${this.token}`
    this.ws = new WebSocket(wsUrl)

    this.ws.onopen = () => {
      console.log('WebSocket connected')
    }

    this.ws.onmessage = (event) => {
      try {
        const message: SignalingMessage = JSON.parse(event.data)
        this.onMessage(message)
      } catch (error) {
        console.error('Error parsing WebSocket message:', error)
      }
    }

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      this.onError(error)
    }

    this.ws.onclose = () => {
      console.log('WebSocket closed')
      this.onClose()
    }
  }

  send(message: SignalingMessage): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message))
    } else {
      console.error('WebSocket is not open')
    }
  }

  close(): void {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }
}

