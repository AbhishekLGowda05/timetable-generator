import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { useDropzone } from 'react-dropzone';
import {
  Upload,
  FileSpreadsheet,
  AlertCircle,
  CheckCircle,
  Download,
  X,
  RefreshCw,
  Loader2,
  Sparkles,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { useToast } from '@/components/ui/use-toast';
import { useUploadStore } from '@/stores';
import { uploadBulkData, downloadFullTemplate, downloadSampleDataset, getSampleData } from '@/lib/api';
import { formatFileSize } from '@/lib/utils';
import type { UploadResponse } from '@/lib/schemas';

const MAX_FILE_SIZE = parseInt(import.meta.env.VITE_MAX_UPLOAD_SIZE_MB || '10') * 1024 * 1024;

export function UploadPage() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isLoadingSample, setIsLoadingSample] = useState(false);
  
  const {
    file,
    setFile,
    uploadId,
    setUploadId,
    preview,
    setPreview,
    validationErrors,
    setValidationErrors,
    isUploading,
    setIsUploading,
    uploadProgress,
    setUploadProgress,
    reset,
    setSchool,
    setTeachers,
    setSubjects,
    setClasses,
    setResources,
  } = useUploadStore();

  const uploadMutation = useMutation({
    mutationFn: async (selectedFile: File) => {
      setIsUploading(true);
      setUploadProgress(0);
      setUploadError(null);
      
      return uploadBulkData(selectedFile, (event) => {
        setUploadProgress(event.percentage);
      });
    },
    onSuccess: (data: UploadResponse) => {
      setIsUploading(false);
      setUploadId(data.upload_id);
      setPreview(data.preview);
      setValidationErrors(data.validation_errors);
      
      if (data.validation_errors.length === 0) {
        toast({
          title: 'Upload Successful',
          description: `Parsed ${data.preview.teachers} teachers, ${data.preview.classes} classes, ${data.preview.subjects} subjects.`,
        });
      } else {
        toast({
          title: 'Upload Complete with Warnings',
          description: `Found ${data.validation_errors.length} validation issues.`,
          variant: 'warning',
        });
      }
    },
    onError: (error: Error) => {
      setIsUploading(false);
      setUploadError(error.message);
      toast({
        title: 'Upload Failed',
        description: error.message,
        variant: 'destructive',
      });
    },
  });

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      const selectedFile = acceptedFiles[0];
      if (!selectedFile) return;

      if (selectedFile.size > MAX_FILE_SIZE) {
        setUploadError(`File size exceeds ${MAX_FILE_SIZE / (1024 * 1024)}MB limit`);
        return;
      }

      setFile(selectedFile);
      setUploadError(null);
      uploadMutation.mutate(selectedFile);
    },
    [setFile, uploadMutation]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls'],
      'text/csv': ['.csv'],
    },
    maxFiles: 1,
    disabled: isUploading,
  });

  const handleRemoveFile = () => {
    reset();
    setUploadError(null);
  };

  // Download template
  const handleDownloadTemplate = async () => {
    setIsDownloading(true);
    try {
      const blob = await downloadFullTemplate();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'timetable_template.xlsx';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast({
        title: 'Template Downloaded',
        description: 'Check your downloads folder for the template file.',
      });
    } catch (error) {
      toast({
        title: 'Download Failed',
        description: error instanceof Error ? error.message : 'Failed to download template',
        variant: 'destructive',
      });
    } finally {
      setIsDownloading(false);
    }
  };

  // Download sample dataset
  const handleDownloadSample = async () => {
    setIsDownloading(true);
    try {
      const blob = await downloadSampleDataset();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'vidya_mandir_sample.xlsx';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast({
        title: 'Sample Dataset Downloaded',
        description: 'Check your downloads folder for the Vidya Mandir sample data.',
      });
    } catch (error) {
      toast({
        title: 'Download Failed',
        description: error instanceof Error ? error.message : 'Failed to download sample',
        variant: 'destructive',
      });
    } finally {
      setIsDownloading(false);
    }
  };

  // Auto-load sample data
  const handleLoadSampleData = async () => {
    setIsLoadingSample(true);
    try {
      const data = await getSampleData();
      
      // Set all the data in the upload store
      setUploadId(data.upload_id);
      setPreview(data.preview);
      setValidationErrors(data.validation_errors);
      setSchool(data.school);
      setTeachers(data.teachers);
      setSubjects(data.subjects);
      setClasses(data.classes);
      setResources(data.resources);
      
      toast({
        title: 'Sample Data Loaded',
        description: `Loaded Vidya Mandir High School data: ${data.preview.teachers} teachers, ${data.preview.classes} classes, ${data.preview.subjects} subjects.`,
      });
    } catch (error) {
      toast({
        title: 'Load Failed',
        description: error instanceof Error ? error.message : 'Failed to load sample data',
        variant: 'destructive',
      });
    } finally {
      setIsLoadingSample(false);
    }
  };

  const handleContinue = () => {
    if (uploadId) {
      navigate('/constraints');
    }
  };

  const downloadErrorCsv = () => {
    if (validationErrors.length === 0) return;
    
    const csvContent = [
      'Row,Field,Message',
      ...validationErrors.map((e) => `${e.row || ''},${e.field || ''},${e.message}`),
    ].join('\n');
    
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'validation_errors.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Upload Data</h1>
        <p className="text-muted-foreground mt-2">
          Upload your school data file to begin generating a timetable.
        </p>
      </div>

      {/* Upload Zone */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Upload className="h-5 w-5" />
            File Upload
          </CardTitle>
          <CardDescription>
            Upload an Excel (.xlsx) or CSV file containing your school data.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!file ? (
            <div
              {...getRootProps()}
              className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                isDragActive
                  ? 'border-primary bg-primary/5'
                  : 'border-muted-foreground/25 hover:border-primary/50'
              }`}
            >
              <input {...getInputProps()} />
              <FileSpreadsheet className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              {isDragActive ? (
                <p className="text-lg font-medium">Drop the file here...</p>
              ) : (
                <>
                  <p className="text-lg font-medium mb-2">
                    Drag and drop your file here, or click to browse
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Supports .xlsx, .xls, and .csv files (max {MAX_FILE_SIZE / (1024 * 1024)}MB)
                  </p>
                </>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              {/* File Info */}
              <div className="flex items-center justify-between p-4 bg-muted/50 rounded-lg">
                <div className="flex items-center gap-3">
                  <FileSpreadsheet className="h-8 w-8 text-primary" />
                  <div>
                    <p className="font-medium">{file.name}</p>
                    <p className="text-sm text-muted-foreground">{formatFileSize(file.size)}</p>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleRemoveFile}
                  disabled={isUploading}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>

              {/* Upload Progress */}
              {isUploading && (
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span>Uploading...</span>
                    <span>{uploadProgress}%</span>
                  </div>
                  <Progress value={uploadProgress} />
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Error Display */}
      {uploadError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Upload Error</AlertTitle>
          <AlertDescription>{uploadError}</AlertDescription>
        </Alert>
      )}

      {/* Preview Card */}
      {preview && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CheckCircle className="h-5 w-5 text-success" />
              Data Preview
            </CardTitle>
            <CardDescription>
              Your file has been parsed successfully. Review the summary below.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-4 bg-muted/50 rounded-lg text-center">
                <p className="text-2xl font-bold text-primary">{preview.teachers}</p>
                <p className="text-sm text-muted-foreground">Teachers</p>
              </div>
              <div className="p-4 bg-muted/50 rounded-lg text-center">
                <p className="text-2xl font-bold text-primary">{preview.classes}</p>
                <p className="text-sm text-muted-foreground">Classes</p>
              </div>
              <div className="p-4 bg-muted/50 rounded-lg text-center">
                <p className="text-2xl font-bold text-primary">{preview.subjects}</p>
                <p className="text-sm text-muted-foreground">Subjects</p>
              </div>
              <div className="p-4 bg-muted/50 rounded-lg text-center">
                <p className="text-2xl font-bold text-primary">{preview.resources}</p>
                <p className="text-sm text-muted-foreground">Resources</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Validation Errors */}
      {validationErrors.length > 0 && (
        <Card className="border-warning">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-warning">
              <AlertCircle className="h-5 w-5" />
              Validation Warnings ({validationErrors.length})
            </CardTitle>
            <CardDescription>
              The following issues were found in your data. You can continue, but consider fixing these.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="max-h-60 overflow-y-auto space-y-2">
                {validationErrors.slice(0, 10).map((error, index) => (
                  <div key={index} className="p-3 bg-warning/10 rounded-md text-sm">
                    <p>
                      {error.row && <span className="font-medium">Row {error.row}: </span>}
                      {error.field && <span className="font-medium">[{error.field}] </span>}
                      {error.message}
                    </p>
                  </div>
                ))}
                {validationErrors.length > 10 && (
                  <p className="text-sm text-muted-foreground">
                    And {validationErrors.length - 10} more issues...
                  </p>
                )}
              </div>
              <Button variant="outline" size="sm" onClick={downloadErrorCsv}>
                <Download className="h-4 w-4 mr-2" />
                Download Error Report
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Download Template */}
      <Card>
        <CardHeader>
          <CardTitle>Need a Template?</CardTitle>
          <CardDescription>
            Download our sample Excel template to see the expected format, or auto-load the sample dataset.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-4">
            <Button 
              variant="outline" 
              onClick={handleDownloadTemplate}
              disabled={isDownloading}
            >
              {isDownloading ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Download className="h-4 w-4 mr-2" />
              )}
              Download Template
            </Button>
            <Button 
              variant="outline"
              onClick={handleDownloadSample}
              disabled={isDownloading}
            >
              {isDownloading ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <FileSpreadsheet className="h-4 w-4 mr-2" />
              )}
              Download Sample Dataset
            </Button>
            <Button 
              variant="default"
              onClick={handleLoadSampleData}
              disabled={isLoadingSample || isUploading}
            >
              {isLoadingSample ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4 mr-2" />
              )}
              Auto-Load Sample Data
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Actions */}
      <div className="flex justify-between">
        <Button variant="outline" onClick={handleRemoveFile} disabled={!file || isUploading}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Start Over
        </Button>
        <Button onClick={handleContinue} disabled={!uploadId || isUploading}>
          Continue to Constraints
        </Button>
      </div>
    </div>
  );
}
