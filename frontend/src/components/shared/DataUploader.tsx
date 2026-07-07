import { useCallback } from 'react'
import { clsx } from 'clsx'
import { useDropzone } from 'react-dropzone'
import { UploadCloud, FileText } from 'lucide-react'
import { fileApi } from '@/services/api'
import { useChatStore } from '@/stores/chatStore'
import { useTranslation } from '@/i18n'
import { toastError, toastSuccess } from '@/stores/toastStore'

export function DataUploader() {
  const { t } = useTranslation()
  const { currentProjectId } = useChatStore()

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      for (const file of acceptedFiles) {
        try {
          const response = await fileApi.uploadFile(file, currentProjectId)
          toastSuccess(t('dataUploader.uploadSuccess', { filename: response.data.filename }))
        } catch (error: any) {
          const detail = error?.response?.data?.detail
          toastError(detail || t('dataUploader.uploadFailed', { filename: file.name }))
        }
      }
    },
    [currentProjectId, t]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/octet-stream': ['.h5ad', '.mtx', '.fastq.gz', '.csv', '.tsv', '.gz', '.rds', '.RData', '.rda'],
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
        {isDragActive ? t('dataUploader.dropToUpload') : t('dataUploader.dragOrClick')}
      </p>
      <p className="mt-1 text-xs text-muted-foreground">
        {t('dataUploader.supportedFormats')}
      </p>
    </div>
  )
}
