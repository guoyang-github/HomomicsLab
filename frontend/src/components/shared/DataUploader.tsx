import { useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { fileApi } from '@/services/api'
import { useChatStore } from '@/stores/chatStore'

export function DataUploader() {
  const { currentProjectId } = useChatStore()

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    for (const file of acceptedFiles) {
      try {
        const response = await fileApi.uploadFile(file, currentProjectId)
        // File uploaded successfully
        alert(`上传成功: ${response.data.filename}`)
      } catch (error) {
        alert(`上传失败: ${file.name}`)
      }
    }
  }, [currentProjectId])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/octet-stream': ['.h5ad', '.mtx', '.fastq.gz'],
    },
  })

  return (
    <div
      {...getRootProps()}
      className={`cursor-pointer rounded-lg border-2 border-dashed p-4 text-center transition-colors ${
        isDragActive
          ? 'border-primary bg-blue-50'
          : 'border-slate-300 hover:border-primary'
      }`}
    >
      <input {...getInputProps()} />
      <p className="text-sm text-slate-600">
        {isDragActive
          ? '释放文件以上传'
          : '拖拽文件到此处，或点击选择文件'}
      </p>
      <p className="mt-1 text-xs text-slate-400">支持 .h5ad, .mtx, .fastq.gz</p>
    </div>
  )
}
