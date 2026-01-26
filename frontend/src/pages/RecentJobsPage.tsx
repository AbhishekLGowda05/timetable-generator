import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  RefreshCw,
  Eye,
  Ban,
  AlertTriangle,
  Calendar,
  ChevronRight,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { useToast } from '@/components/ui/use-toast';
import { listJobs, cancelJob, rerunJob } from '@/lib/api';
import { formatDateTime, formatDuration, cn } from '@/lib/utils';

// Types
interface JobListItem {
  job_id: string;
  status: 'queued' | 'running' | 'diagnostics' | 'completed' | 'failed' | 'cancelled';
  created_at?: string;
  started_at?: string;
  completed_at?: string;
  school_name?: string;
  classes_count?: number;
  teachers_count?: number;
  error?: string;
  progress?: number;
}

const STATUS_CONFIG: Record<
  string,
  { icon: React.ElementType; color: string; bgColor: string; label: string }
> = {
  queued: {
    icon: Clock,
    color: 'text-muted-foreground',
    bgColor: 'bg-muted/50',
    label: 'Queued',
  },
  running: {
    icon: Loader2,
    color: 'text-primary',
    bgColor: 'bg-primary/10',
    label: 'Running',
  },
  diagnostics: {
    icon: Loader2,
    color: 'text-amber-600',
    bgColor: 'bg-amber-50',
    label: 'Diagnostics',
  },
  completed: {
    icon: CheckCircle,
    color: 'text-green-600',
    bgColor: 'bg-green-50',
    label: 'Completed',
  },
  failed: {
    icon: XCircle,
    color: 'text-destructive',
    bgColor: 'bg-destructive/10',
    label: 'Failed',
  },
  cancelled: {
    icon: Ban,
    color: 'text-muted-foreground',
    bgColor: 'bg-muted/30',
    label: 'Cancelled',
  },
};

export function RecentJobsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [expandedJob, setExpandedJob] = useState<string | null>(null);

  // Fetch job list
  const {
    data: jobsData,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['jobs'],
    queryFn: listJobs,
    refetchInterval: 10000, // Poll every 10s
  });

  // Cancel mutation
  const cancelMutation = useMutation({
    mutationFn: (jobId: string) => cancelJob(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      toast({
        title: 'Job Cancelled',
        description: 'The job has been cancelled.',
      });
    },
    onError: (err: Error) => {
      toast({
        title: 'Cancel Failed',
        description: err.message,
        variant: 'destructive',
      });
    },
  });

  // Rerun mutation
  const rerunMutation = useMutation({
    mutationFn: (jobId: string) => rerunJob(jobId),
    onSuccess: () => {
      toast({
        title: 'Job Resubmitted',
        description: 'A new job has been created.',
      });
      navigate('/generate');
    },
    onError: (err: Error) => {
      toast({
        title: 'Rerun Failed',
        description: err.message,
        variant: 'destructive',
      });
    },
  });

  const handleViewResult = (jobId: string) => {
    navigate(`/results/${jobId}`);
  };

  const handleCancel = (jobId: string) => {
    cancelMutation.mutate(jobId);
  };

  const handleRerun = (jobId: string) => {
    rerunMutation.mutate(jobId);
  };

  const jobs: JobListItem[] = jobsData?.jobs ?? [];

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <Loader2 className="h-12 w-12 animate-spin text-primary mx-auto mb-4" />
          <p className="text-muted-foreground">Loading recent jobs...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="max-w-4xl mx-auto">
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Failed to Load Jobs</AlertTitle>
          <AlertDescription>
            {error instanceof Error ? error.message : 'Could not load job list.'}
          </AlertDescription>
        </Alert>
        <div className="flex gap-4 mt-6">
          <Button onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Retry
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Recent Jobs</h1>
          <p className="text-muted-foreground mt-1">
            View and manage your timetable generation jobs
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button onClick={() => navigate('/upload')}>
            Create New Job
            <ChevronRight className="h-4 w-4 ml-2" />
          </Button>
        </div>
      </div>

      {/* Stats Summary */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {['queued', 'running', 'completed', 'failed', 'cancelled'].map((status) => {
          const count = jobs.filter((j) => j.status === status).length;
          const config = STATUS_CONFIG[status];
          const Icon = config.icon;
          return (
            <Card key={status} className="p-4">
              <div className="flex items-center gap-3">
                <div className={cn('p-2 rounded-lg', config.bgColor)}>
                  <Icon
                    className={cn(
                      'h-5 w-5',
                      config.color,
                      status === 'running' && 'animate-spin'
                    )}
                  />
                </div>
                <div>
                  <p className="text-2xl font-bold">{count}</p>
                  <p className="text-xs text-muted-foreground">{config.label}</p>
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      {/* Jobs Table */}
      {jobs.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center">
            <Calendar className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-medium mb-2">No Jobs Yet</h3>
            <p className="text-muted-foreground mb-6">
              You haven't created any timetable generation jobs yet.
            </p>
            <Button onClick={() => navigate('/upload')}>
              Create Your First Job
              <ChevronRight className="h-4 w-4 ml-2" />
            </Button>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Job History</CardTitle>
            <CardDescription>
              {jobs.length} job{jobs.length !== 1 ? 's' : ''} found
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Job ID</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>School</TableHead>
                  <TableHead>Size</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobs.map((job) => {
                  const config = STATUS_CONFIG[job.status];
                  const Icon = config.icon;
                  const isActive = job.status === 'queued' || job.status === 'running';
                  const duration =
                    job.started_at && job.completed_at
                      ? (new Date(job.completed_at).getTime() -
                          new Date(job.started_at).getTime()) /
                        1000
                      : null;

                  return (
                    <TableRow
                      key={job.job_id}
                      className={cn(
                        'cursor-pointer hover:bg-muted/50',
                        expandedJob === job.job_id && 'bg-muted/30'
                      )}
                      onClick={() =>
                        setExpandedJob(expandedJob === job.job_id ? null : job.job_id)
                      }
                    >
                      <TableCell className="font-mono text-sm">
                        {job.job_id.slice(0, 8)}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Icon
                            className={cn(
                              'h-4 w-4',
                              config.color,
                              job.status === 'running' && 'animate-spin'
                            )}
                          />
                          <span className={config.color}>{config.label}</span>
                        </div>
                      </TableCell>
                      <TableCell>{job.school_name || '—'}</TableCell>
                      <TableCell>
                        {job.classes_count && job.teachers_count
                          ? `${job.classes_count}C / ${job.teachers_count}T`
                          : '—'}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {job.created_at ? formatDateTime(job.created_at) : '—'}
                      </TableCell>
                      <TableCell>
                        {duration ? formatDuration(duration) : '—'}
                      </TableCell>
                      <TableCell className="text-right">
                        <div
                          className="flex justify-end gap-1"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <TooltipProvider>
                            {job.status === 'completed' && (
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => handleViewResult(job.job_id)}
                                  >
                                    <Eye className="h-4 w-4" />
                                  </Button>
                                </TooltipTrigger>
                                <TooltipContent>View Results</TooltipContent>
                              </Tooltip>
                            )}
                            {isActive && (
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => handleCancel(job.job_id)}
                                  >
                                    <Ban className="h-4 w-4" />
                                  </Button>
                                </TooltipTrigger>
                                <TooltipContent>Cancel</TooltipContent>
                              </Tooltip>
                            )}
                            {(job.status === 'failed' || job.status === 'cancelled') && (
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => handleRerun(job.job_id)}
                                  >
                                    <RefreshCw className="h-4 w-4" />
                                  </Button>
                                </TooltipTrigger>
                                <TooltipContent>Rerun</TooltipContent>
                              </Tooltip>
                            )}
                          </TooltipProvider>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Create New Job CTA */}
      <Card className="bg-primary/5 border-primary/20">
        <CardContent className="py-8 text-center">
          <h3 className="text-lg font-medium mb-2">Ready to Generate a New Timetable?</h3>
          <p className="text-muted-foreground mb-4">
            Upload your school data and let our solver create an optimized schedule.
          </p>
          <Button onClick={() => navigate('/upload')}>
            Start New Generation
            <ChevronRight className="h-4 w-4 ml-2" />
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
