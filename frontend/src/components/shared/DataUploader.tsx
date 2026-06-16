import { useCallback } from 'react'
import { clsx } from 'clsx'
import { useDropzone } from 'react-dropzone'
import { UploadCloud, FileText } from 'lucide-react'
import { fileApi } from '@/services/api'
import { useChatStore } from '@/stores/chatStore'
import { toastError, toastSuccess } from '@/stores/toastStore'

export function DataUploader() {
  const { currentProjectId } = useChatStore()

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      for (const file of acceptedFiles) {
        try {
          const response = await fileApi.uploadFile(file, currentProjectId)
          toastSuccess(`${response.data.filename} 上传成功`)
        } catch (error: any) {
          const detail = error?.response?.data?.detail
          toastError(detail || `${file.name} 上传失败`)
        }
      }
    },
    [currentProjectId]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/octet-stream': ['.h5ad', '.mtx', '.fastq.gz', '.csv', '.tsv', '.gz'],
      'text/csv': ['.csv'],
      'text/tab-separated-values': ['.tsv'],
    },
  })

  return (
    <div
      {...getRootProps()}
      className={clsx(
        'cursor-pointer rounded-xl border-2 border-dashed p-6 text-center transition-colors',
        isDragActive
          ? 'border-primary bg-primary/5'
          : 'border-border bg-muted/50 hover:border-primary/50 hover:bg-muted'
      )}
    >
      <input {...getInputProps()} />
      <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
        {isDragActive ? <FileText className="h-5 w-5" /> : <UploadCloud className="h-5 w-5" />}
      </div>
      <p className="text-sm font-medium text-foreground">
        {isDragActive ? '释放文件以上传' : '拖拽或点击上传数据'}
      </p>
      <p className="mt-1 text-xs text-muted-foreground">
        支持 .h5ad, .mtx, .csv, .tsv, .fastq.gz
      </p>
    </div>
  )
}
