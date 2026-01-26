import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
  Play,
  Loader2,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Clock,
  ChevronLeft,
  Ban,
  RefreshCw,
  Download,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { useToast } from '@/components/ui/use-toast';
import { useUploadStore, useConstraintsStore, useJobStore } from '@/stores';
import { createJobFromUpload, getJobStatus, cancelJob } from '@/lib/api';
import { formatDuration, formatDateTime } from '@/lib/utils';
import { get } from '@/lib/api-client';

const STATUS_CONFIG: Record<string, { icon: React.ElementType; color: string; label: string }> = {
  queued: { icon: Clock, color: 'text-muted-foreground', label: 'Queued' },
  running: { icon: Loader2, color: 'text-primary', label: 'Running' },
  diagnostics: { icon: AlertTriangle, color: 'text-warning', label: 'Diagnostics' },
  completed: { icon: CheckCircle, color: 'text-success', label: 'Completed' },
  failed: { icon: XCircle, color: 'text-destructive', label: 'Failed' },
  cancelled: { icon: Ban, color: 'text-muted-foreground', label: 'Cancelled' },
};

export function GeneratePage() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { uploadId, preview, setUploadId, setPreview, setSchool, setTeachers, setSubjects, setClasses, setResources } = useUploadStore();
  const { constraints, setConstraints } = useConstraintsStore();
  const {
    currentJobId,
    status,
    progress,
    logs,
    error,
    createdAt,
    startedAt,
    completedAt,
    setCurrentJob,
    setStatus,
    setProgress,
    setLogs,
    setError,
    setTimestamps,
    reset: resetJob,
  } = useJobStore();

  // Load sample data mutation
  const loadSampleDataMutation = useMutation({
    mutationFn: async () => {
      const data = await get<{
        upload_id: string;
        preview: { teachers: number; classes: number; subjects: number; resources: number };
        school: unknown;
        teachers: unknown[];
        subjects: unknown[];
        classes: unknown[];
        resources: unknown[];
        constraints: unknown;
      }>('/api/v1/timetable/sample-data');
      return data;
    },
    onSuccess: (data) => {
      setUploadId(data.upload_id);
      setPreview(data.preview);
      setSchool(data.school as never);
      setTeachers(data.teachers as never[]);
      setSubjects(data.subjects as never[]);
      setClasses(data.classes as never[]);
      setResources(data.resources as never[]);
      if (data.constraints) {
        setConstraints(data.constraints as never);
      }
      toast({
        title: 'Sample Data Loaded',
        description: 'Vidya Mandir High School sample data is ready to use.',
      });
    },
    onError: (err: Error) => {
      toast({
        title: 'Failed to Load Sample Data',
        description: err.message,
        variant: 'destructive',
      });
    },
  });

  // Create job mutation
  const createJobMutation = useMutation({
    mutationFn: async () => {
      if (!uploadId) throw new Error('No upload ID');
      return createJobFromUpload(uploadId, constraints, {
        time_limit_seconds: 120,
        force_fresh: true,  // Always force fresh solve when constraints may have changed
        demo_mode: true,    // In demo mode, use higher time limits
      });
    },
    onSuccess: (data) => {
      setCurrentJob(data.job_id);
      setStatus('queued');
      setTimestamps({ createdAt: new Date().toISOString() });
      toast({
        title: 'Job Created',
        description: `Job ${data.job_id.slice(0, 8)} has been queued.`,
      });
    },
    onError: (err: Error) => {
      toast({
        title: 'Failed to Create Job',
        description: err.message,
        variant: 'destructive',
      });
    },
  });

  // Cancel job mutation
  const cancelJobMutation = useMutation({
    mutationFn: async () => {
      if (!currentJobId) throw new Error('No job to cancel');
      return cancelJob(currentJobId);
    },
    onSuccess: () => {
      setStatus('cancelled');
      toast({
        title: 'Job Cancelled',
        description: 'The generation job has been cancelled.',
      });
    },
    onError: (err: Error) => {
      // If job not found, it might have already completed
      if (err.message.includes('404')) {
        toast({
          title: 'Unable to Cancel',
          description: 'The job may have already completed or the server was restarted.',
          variant: 'default',
        });
        // Reset job state since job is gone
        resetJob();
      } else {
        toast({
          title: 'Failed to Cancel',
          description: err.message,
          variant: 'destructive',
        });
      }
    },
  });

  // Poll for job status
  const statusQuery = useQuery({
    queryKey: ['jobStatus', currentJobId],
    queryFn: () => getJobStatus(currentJobId!),
    enabled: !!currentJobId && status !== 'completed' && status !== 'failed' && status !== 'cancelled',
    refetchInterval: (query) => {
      // Exponential backoff: 1s, 2s, 4s... max 10s
      const data = query.state.data;
      if (data?.status === 'completed' || data?.status === 'failed') {
        return false;
      }
      return Math.min(1000 * Math.pow(2, query.state.dataUpdateCount), 10000);
    },
    retry: (failureCount, error) => {
      // Only retry 404 once or twice - if job doesn't exist, it likely never will
      if (error instanceof Error && error.message.includes('404')) {
        return failureCount < 2;
      }
      // Default retry behavior
      return failureCount < 3;
    },
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 5000),
  });

  // Handle query errors (e.g., job not found after retries)
  useEffect(() => {
    if (statusQuery.error) {
      const errorMessage = statusQuery.error instanceof Error ? statusQuery.error.message : 'Unknown error';
      if (errorMessage.includes('404')) {
        // Job not found - reset state and inform user
        setError('Job not found. The server may have restarted or the job expired.');
        setStatus('failed');
        toast({
          title: 'Job Not Found',
          description: 'The job may have expired or the server was restarted. Please create a new job.',
          variant: 'destructive',
        });
        // Reset the job state so user can start fresh
        resetJob();
      }
    }
  }, [statusQuery.error, setError, setStatus, toast, resetJob]);

  // Update store when status query returns
  useEffect(() => {
    if (statusQuery.data) {
      const data = statusQuery.data;
      setStatus(data.status as typeof status);
      setProgress(data.progress);
      if (data.logs) setLogs(data.logs);
      if (data.error) setError(data.error);
      setTimestamps({
        startedAt: data.started_at || undefined,
        completedAt: data.completed_at || undefined,
      });

      // Navigate to results on completion
      if (data.status === 'completed') {
        toast({
          title: 'Timetable Generated!',
          description: 'Your timetable is ready to view.',
        });
        setTimeout(() => navigate(`/results/${currentJobId}`), 1500);
      }
    }
  }, [statusQuery.data, setStatus, setProgress, setLogs, setError, setTimestamps, currentJobId, navigate, toast]);

  const handleGenerate = () => {
    if (!uploadId) {
      toast({
        title: 'No Data Uploaded',
        description: 'Please upload your school data first.',
        variant: 'destructive',
      });
      navigate('/upload');
      return;
    }
    createJobMutation.mutate();
  };

  const handleCancel = () => {
    cancelJobMutation.mutate();
  };

  const handleNewJob = () => {
    resetJob();
    handleGenerate();
  };

  const handleViewResults = () => {
    if (currentJobId) {
      navigate(`/results/${currentJobId}`);
    }
  };

  const isJobActive = status === 'queued' || status === 'running' || status === 'diagnostics';
  const isJobComplete = status === 'completed' || status === 'failed' || status === 'cancelled';
  const StatusIcon = status ? STATUS_CONFIG[status]?.icon : null;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Generate Timetable</h1>
        <p className="text-muted-foreground mt-2">
          Submit your data to the solver and generate an optimal timetable.
        </p>
      </div>

      {/* Pre-submit Summary */}
      {!currentJobId && (
        <Card>
          <CardHeader>
            <CardTitle>Ready to Generate</CardTitle>
            <CardDescription>
              Review your configuration before starting the solver.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Data Summary */}
            {preview ? (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-4 bg-muted/50 rounded-lg text-center">
                  <p className="text-2xl font-bold">{preview.teachers}</p>
                  <p className="text-sm text-muted-foreground">Teachers</p>
                </div>
                <div className="p-4 bg-muted/50 rounded-lg text-center">
                  <p className="text-2xl font-bold">{preview.classes}</p>
                  <p className="text-sm text-muted-foreground">Classes</p>
                </div>
                <div className="p-4 bg-muted/50 rounded-lg text-center">
                  <p className="text-2xl font-bold">{preview.subjects}</p>
                  <p className="text-sm text-muted-foreground">Subjects</p>
                </div>
                <div className="p-4 bg-muted/50 rounded-lg text-center">
                  <p className="text-2xl font-bold">{preview.resources}</p>
                  <p className="text-sm text-muted-foreground">Resources</p>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <Alert variant="warning">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertTitle>No Data Uploaded</AlertTitle>
                  <AlertDescription>
                    Upload your school data or use our sample dataset to try the generator.
                  </AlertDescription>
                </Alert>
                
                {/* Quick start buttons */}
                <div className="flex flex-col sm:flex-row justify-center gap-3">
                  <Button
                    variant="default"
                    onClick={() => loadSampleDataMutation.mutate()}
                    disabled={loadSampleDataMutation.isPending}
                  >
                    {loadSampleDataMutation.isPending ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Loading Sample Data...
                      </>
                    ) : (
                      <>
                        <Download className="h-4 w-4 mr-2" />
                        Use Sample Data
                      </>
                    )}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => navigate('/upload')}
                  >
                    <ChevronLeft className="h-4 w-4 mr-2 rotate-180" />
                    Upload Your Data
                  </Button>
                </div>
              </div>
            )}

            {/* Estimated Time */}
            <div className="flex items-center justify-between p-4 bg-muted/30 rounded-lg">
              <div className="flex items-center gap-2">
                <Clock className="h-5 w-5 text-muted-foreground" />
                <span className="text-sm">Estimated generation time:</span>
              </div>
              <span className="font-medium">
                {preview ? `${Math.max(10, preview.classes * 2)}-${Math.max(30, preview.classes * 5)}s` : 'N/A'}
              </span>
            </div>

            {/* Generate Button */}
            <div className="flex justify-center pt-4">
              <Button
                size="lg"
                onClick={handleGenerate}
                disabled={!uploadId || createJobMutation.isPending}
              >
                {createJobMutation.isPending ? (
                  <>
                    <Loader2 className="h-5 w-5 mr-2 animate-spin" />
                    Starting...
                  </>
                ) : (
                  <>
                    <Play className="h-5 w-5 mr-2" />
                    Generate Timetable
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Job Status Panel */}
      {currentJobId && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  {StatusIcon && (
                    <StatusIcon
                      className={`h-5 w-5 ${STATUS_CONFIG[status!]?.color} ${
                        status === 'running' ? 'animate-spin' : ''
                      }`}
                    />
                  )}
                  Job {currentJobId.slice(0, 8)}
                </CardTitle>
                <CardDescription>
                  Status: {STATUS_CONFIG[status!]?.label || 'Unknown'}
                </CardDescription>
              </div>
              {isJobActive && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleCancel}
                  disabled={cancelJobMutation.isPending}
                >
                  <Ban className="h-4 w-4 mr-2" />
                  Cancel
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Progress Bar */}
            {isJobActive && (
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Progress</span>
                  <span>{progress}%</span>
                </div>
                <Progress value={progress} />
              </div>
            )}

            {/* Timestamps */}
            <div className="grid grid-cols-3 gap-4 text-sm">
              {createdAt && (
                <div>
                  <p className="text-muted-foreground">Created</p>
                  <p className="font-medium">{formatDateTime(createdAt)}</p>
                </div>
              )}
              {startedAt && (
                <div>
                  <p className="text-muted-foreground">Started</p>
                  <p className="font-medium">{formatDateTime(startedAt)}</p>
                </div>
              )}
              {completedAt && (
                <div>
                  <p className="text-muted-foreground">Completed</p>
                  <p className="font-medium">{formatDateTime(completedAt)}</p>
                </div>
              )}
            </div>

            {/* Duration */}
            {startedAt && completedAt && (
              <div className="p-3 bg-muted/30 rounded-lg text-center">
                <p className="text-sm text-muted-foreground">Total Duration</p>
                <p className="text-lg font-medium">
                  {formatDuration(
                    (new Date(completedAt).getTime() - new Date(startedAt).getTime()) / 1000
                  )}
                </p>
              </div>
            )}

            {/* Error Message */}
            {error && (
              <Alert variant="destructive">
                <XCircle className="h-4 w-4" />
                <AlertTitle>Generation Failed</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {/* Logs */}
            {logs.length > 0 && (
              <div className="space-y-2">
                <p className="text-sm font-medium">Logs</p>
                <div className="max-h-40 overflow-y-auto bg-muted/30 rounded-lg p-3 font-mono text-xs">
                  {logs.map((log, i) => (
                    <div key={i} className="py-0.5">
                      <span className="text-muted-foreground">[{log.t}]</span> {log.message}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Actions */}
            {isJobComplete && (
              <div className="flex justify-center gap-4 pt-4">
                {status === 'completed' && (
                  <Button onClick={handleViewResults}>
                    <CheckCircle className="h-4 w-4 mr-2" />
                    View Results
                  </Button>
                )}
                <Button variant="outline" onClick={handleNewJob}>
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Generate New
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Navigation */}
      <div className="flex justify-between">
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate('/constraints')}>
            <ChevronLeft className="h-4 w-4 mr-2" />
            Back to Constraints
          </Button>
          {currentJobId && (
            <Button 
              variant="ghost" 
              size="sm"
              onClick={() => {
                resetJob();
                toast({
                  title: 'Job Cleared',
                  description: 'You can now start a new job.',
                });
              }}
            >
              <RefreshCw className="h-4 w-4 mr-2" />
              Start Fresh
            </Button>
          )}
        </div>
        {status === 'completed' && currentJobId && (
          <Button onClick={handleViewResults}>
            View Results
          </Button>
        )}
      </div>
    </div>
  );
}
