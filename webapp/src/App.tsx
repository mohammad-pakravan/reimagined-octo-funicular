import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import VideoCall from './components/VideoCall'
import Loading from './components/Loading'
import Error from './components/Error'
import { verifyToken } from './services/api'

function App() {
  const [searchParams] = useSearchParams()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [roomId, setRoomId] = useState<string | null>(null)

  useEffect(() => {
    // Extract room_id and token from URL
    const roomIdParam = searchParams.get('room_id') || window.location.pathname.split('/').pop()
    const tokenParam = searchParams.get('token')

    if (!roomIdParam || !tokenParam) {
      setError('لینک معتبر نیست. room_id و token یافت نشد.')
      setLoading(false)
      return
    }

    setRoomId(roomIdParam)
    setToken(tokenParam)

    // Verify token and get room info
    verifyToken(roomIdParam, tokenParam)
      .then(() => {
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message || 'خطا در تایید دسترسی')
        setLoading(false)
      })
  }, [searchParams])

  if (loading) {
    return <Loading />
  }

  if (error) {
    return <Error message={error} />
  }

  if (!token || !roomId) {
    return <Error message="اطلاعات تماس یافت نشد." />
  }

  return <VideoCall roomId={roomId} token={token} />
}

export default App

