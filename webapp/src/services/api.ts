import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export interface VerifyTokenResponse {
  authorized: boolean
  user_id: number
  room_id: string
  call_type: string
  chat_room_id: number
}

export async function verifyToken(roomId: string, token: string): Promise<VerifyTokenResponse> {
  const response = await axios.get<VerifyTokenResponse>(
    `${API_BASE_URL}/api/video-call/${roomId}/verify`,
    {
      params: { token },
    }
  )
  return response.data
}

