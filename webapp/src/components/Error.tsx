interface ErrorProps {
  message: string
}

export default function Error({ message }: ErrorProps) {
  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-900">
      <div className="text-center bg-red-900/20 border border-red-500 rounded-lg p-8 max-w-md mx-4">
        <div className="text-red-500 text-4xl mb-4">❌</div>
        <h1 className="text-red-400 text-xl font-bold mb-2">خطا</h1>
        <p className="text-white">{message}</p>
      </div>
    </div>
  )
}

