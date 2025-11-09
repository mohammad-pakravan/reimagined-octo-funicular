import { useEffect, useRef, useState } from 'react'
import SimplePeer from 'simple-peer'
import { SignalingClient } from '../services/websocket'

interface VideoCallProps {
  roomId: string
  token: string
}

export default function VideoCall({ roomId, token }: VideoCallProps) {
  const [isVideoEnabled, setIsVideoEnabled] = useState(true)
  const [isAudioEnabled, setIsAudioEnabled] = useState(true)
  const [callType, setCallType] = useState<'video' | 'voice'>('video')
  const [isConnected, setIsConnected] = useState(false)

  const localVideoRef = useRef<HTMLVideoElement>(null)
  const remoteVideoRef = useRef<HTMLVideoElement>(null)
  const localStreamRef = useRef<MediaStream | null>(null)
  const peerRef = useRef<SimplePeer.Instance | null>(null)
  const signalingRef = useRef<SignalingClient | null>(null)

  useEffect(() => {
    initializeCall()

    return () => {
      cleanup()
    }
  }, [roomId, token])

  const initializeCall = async () => {
    try {
      // Get user media
      const constraints: MediaStreamConstraints = {
        video: callType === 'video',
        audio: true,
      }

      const stream = await navigator.mediaDevices.getUserMedia(constraints)
      localStreamRef.current = stream

      if (localVideoRef.current) {
        localVideoRef.current.srcObject = stream
      }

      // Determine call type (should come from API)
      // For now, assume video if video is available
      setCallType(stream.getVideoTracks().length > 0 ? 'video' : 'voice')

      // Setup WebSocket signaling
      setupSignaling()
    } catch (error) {
      console.error('Error accessing media devices:', error)
      alert('خطا در دسترسی به دوربین/میکروفون')
    }
  }

  const setupSignaling = () => {
    signalingRef.current = new SignalingClient(
      roomId,
      token,
      handleSignalingMessage,
      handleSignalingError,
      handleSignalingClose
    )

    signalingRef.current.connect()

    // Wait a bit for connection, then create peer
    setTimeout(() => {
      if (signalingRef.current) {
        createPeer()
      }
    }, 1000)
  }

  const createPeer = () => {
    // Determine if we're the initiator (first to join)
    // In a 1-to-1 call, we can make the first user the initiator
    // We'll determine this based on when we receive a message
    let isInitiator = true
    
    // If we already have a peer, don't create another
    if (peerRef.current) {
      return
    }

    const peer = new SimplePeer({
      initiator: isInitiator,
      trickle: false,
      stream: localStreamRef.current || undefined,
      config: {
        iceServers: [
          { urls: 'stun:stun.l.google.com:19302' },
          { urls: 'stun:stun1.l.google.com:19302' },
        ],
      },
    })

    setupPeerHandlers(peer)
    peerRef.current = peer
  }

  const handleSignalingMessage = (message: any) => {
    if (message.type === 'user-joined') {
      console.log('Other user joined')
      // When other user joins, create peer if we're the initiator
      if (!peerRef.current) {
        createPeer()
      }
    } else if (message.type === 'offer' && peerRef.current) {
      // If we receive an offer, we're not the initiator
      // Recreate peer as non-initiator
      if (peerRef.current) {
        peerRef.current.destroy()
      }
      const peer = new SimplePeer({
        initiator: false,
        trickle: false,
        stream: localStreamRef.current || undefined,
        config: {
          iceServers: [
            { urls: 'stun:stun.l.google.com:19302' },
            { urls: 'stun:stun1.l.google.com:19302' },
          ],
        },
      })
      setupPeerHandlers(peer)
      peerRef.current = peer
      peer.signal(message.sdp)
    } else if (message.type === 'answer' && peerRef.current) {
      peerRef.current.signal(message.sdp)
    } else if (message.type === 'ice-candidate' && peerRef.current) {
      peerRef.current.signal(message.candidate)
    } else if (message.type === 'user-left') {
      console.log('Other user left')
      setIsConnected(false)
    } else if (message.type === 'call-ended') {
      handleEndCall()
    }
  }

  const setupPeerHandlers = (peer: SimplePeer.Instance) => {
    peer.on('signal', (data) => {
      if (signalingRef.current) {
        if (data.type === 'offer') {
          signalingRef.current.send({
            type: 'offer',
            sdp: data,
          })
        } else if (data.type === 'answer') {
          signalingRef.current.send({
            type: 'answer',
            sdp: data,
          })
        }
      }
    })

    peer.on('stream', (stream) => {
      if (remoteVideoRef.current) {
        remoteVideoRef.current.srcObject = stream
      }
      setIsConnected(true)
    })

    peer.on('connect', () => {
      console.log('Peer connected')
      setIsConnected(true)
    })

    peer.on('error', (err) => {
      console.error('Peer error:', err)
    })
  }

  const handleSignalingError = (error: Event) => {
    console.error('Signaling error:', error)
  }

  const handleSignalingClose = () => {
    console.log('Signaling closed')
    setIsConnected(false)
  }

  const toggleVideo = () => {
    if (localStreamRef.current) {
      const videoTrack = localStreamRef.current.getVideoTracks()[0]
      if (videoTrack) {
        videoTrack.enabled = !isVideoEnabled
        setIsVideoEnabled(!isVideoEnabled)
      }
    }
  }

  const toggleAudio = () => {
    if (localStreamRef.current) {
      const audioTrack = localStreamRef.current.getAudioTracks()[0]
      if (audioTrack) {
        audioTrack.enabled = !isAudioEnabled
        setIsAudioEnabled(!isAudioEnabled)
      }
    }
  }

  const handleEndCall = () => {
    cleanup()
    // Notify backend
    if (signalingRef.current) {
      signalingRef.current.send({ type: 'call-ended' })
    }
    window.close()
  }

  const cleanup = () => {
    // Stop local stream
    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach((track) => track.stop())
      localStreamRef.current = null
    }

    // Destroy peer
    if (peerRef.current) {
      peerRef.current.destroy()
      peerRef.current = null
    }

    // Close signaling
    if (signalingRef.current) {
      signalingRef.current.close()
      signalingRef.current = null
    }
  }

  return (
    <div className="flex flex-col h-screen bg-gray-900 text-white">
      {/* Video Area */}
      <div className="flex-1 relative">
        {/* Remote Video */}
        <video
          ref={remoteVideoRef}
          autoPlay
          playsInline
          className={`w-full h-full object-cover ${callType === 'voice' ? 'hidden' : ''}`}
        />

        {/* Local Video (Picture-in-Picture) */}
        {callType === 'video' && (
          <div className="absolute bottom-4 right-4 w-64 h-48 rounded-lg overflow-hidden shadow-lg">
            <video
              ref={localVideoRef}
              autoPlay
              playsInline
              muted
              className="w-full h-full object-cover"
            />
          </div>
        )}

        {/* Connection Status */}
        {!isConnected && (
          <div className="absolute top-4 left-4 bg-yellow-600 text-white px-4 py-2 rounded-lg">
            در حال اتصال...
          </div>
        )}
      </div>

      {/* Controls */}
      <div className="bg-gray-800 p-4 flex justify-center items-center gap-4">
        <button
          onClick={toggleAudio}
          className={`p-4 rounded-full ${
            isAudioEnabled ? 'bg-green-600' : 'bg-red-600'
          } hover:opacity-80 transition`}
        >
          {isAudioEnabled ? '🎤' : '🔇'}
        </button>

        {callType === 'video' && (
          <button
            onClick={toggleVideo}
            className={`p-4 rounded-full ${
              isVideoEnabled ? 'bg-green-600' : 'bg-red-600'
            } hover:opacity-80 transition`}
          >
            {isVideoEnabled ? '📹' : '📵'}
          </button>
        )}

        <button
          onClick={handleEndCall}
          className="p-4 rounded-full bg-red-600 hover:opacity-80 transition"
        >
          📞
        </button>
      </div>
    </div>
  )
}

