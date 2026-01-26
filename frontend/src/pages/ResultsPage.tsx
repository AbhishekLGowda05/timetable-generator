import { useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  RefreshCw,
  Loader2,
  AlertTriangle,
  Users,
  User,
  Building2,
  ChevronLeft,
  ChevronRight,
  FileSpreadsheet,
  FileJson,
  Printer,
  X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { useToast } from '@/components/ui/use-toast';
import { getJobResult, rerunJob, downloadResult } from '@/lib/api';
import { cn, formatTime } from '@/lib/utils';
import type { JobResultResponse, TimetablePeriod, Diagnostic } from '@/lib/schemas';

// Extended period interface for display purposes
interface DisplayPeriod {
  period: number;
  subject_id: string;
  subject_name?: string;
  teacher_id: string;
  teacher_name?: string;
  day: string;
  class_id?: string;
  class_name?: string;
  room_id?: string;
  room_name?: string;
  is_block_start?: boolean;
  is_block_continuation?: boolean;
  start_time?: string;
  end_time?: string;
  resource_id?: string;
}

// Day and period configuration - Must match backend day abbreviations
const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const DAY_NAMES: Record<string, string> = {
  'Mon': 'Monday',
  'Tue': 'Tuesday',
  'Wed': 'Wednesday',
  'Thu': 'Thursday',
  'Fri': 'Friday',
  'Sat': 'Saturday',
};

// Color palette for subjects
const SUBJECT_COLORS = [
  'bg-blue-100 border-blue-300 text-blue-900',
  'bg-green-100 border-green-300 text-green-900',
  'bg-purple-100 border-purple-300 text-purple-900',
  'bg-orange-100 border-orange-300 text-orange-900',
  'bg-pink-100 border-pink-300 text-pink-900',
  'bg-teal-100 border-teal-300 text-teal-900',
  'bg-indigo-100 border-indigo-300 text-indigo-900',
  'bg-amber-100 border-amber-300 text-amber-900',
  'bg-cyan-100 border-cyan-300 text-cyan-900',
  'bg-rose-100 border-rose-300 text-rose-900',
];

export function ResultsPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();

  const [activeTab, setActiveTab] = useState('classes');
  const [selectedEntity, setSelectedEntity] = useState<string>('');
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [selectedPeriod, setSelectedPeriod] = useState<DisplayPeriod | null>(null);

  // Fetch results
  const {
    data: result,
    isLoading,
    error,
    refetch,
  } = useQuery<JobResultResponse>({
    queryKey: ['jobResult', jobId],
    queryFn: () => getJobResult(jobId!),
    enabled: !!jobId,
    staleTime: Infinity, // Results don't change
  });

  // Rerun mutation
  const rerunMutation = useMutation({
    mutationFn: () => rerunJob(jobId!),
    onSuccess: () => {
      toast({
        title: 'Job Resubmitted',
        description: 'Redirecting to generation page...',
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

  // Build subject color map
  const subjectColorMap = useMemo(() => {
    if (!result) return {};
    const subjects = new Set<string>();
    const timetable = result.timetable_json?.timetable || {};
    Object.values(timetable).forEach((daySchedules) => {
      if (daySchedules && typeof daySchedules === 'object') {
        Object.values(daySchedules).forEach((periods: TimetablePeriod[]) => {
          if (Array.isArray(periods)) {
            periods.forEach((p) => subjects.add(p.subject_id));
          }
        });
      }
    });
    const map: Record<string, string> = {};
    Array.from(subjects).forEach((subjectId, i) => {
      map[subjectId] = SUBJECT_COLORS[i % SUBJECT_COLORS.length];
    });
    return map;
  }, [result]);

  // Get entities for current tab
  const entities = useMemo(() => {
    if (!result) return [];
    const timetable = result.timetable_json?.timetable || {};
    const teacherSchedules = result.timetable_json?.teacher_schedules || {};
    const resourceViews = result.timetable_json?.resource_views || {};
    switch (activeTab) {
      case 'classes':
        return Object.keys(timetable).sort();
      case 'teachers':
        return Object.keys(teacherSchedules).sort();
      case 'resources':
        return Object.keys(resourceViews).sort();
      default:
        return [];
    }
  }, [result, activeTab]);

  // Get periods for selected entity (flatten the nested structure)
  const periods = useMemo((): DisplayPeriod[] => {
    if (!result || !selectedEntity) return [];
    const timetable = result.timetable_json?.timetable || {};
    const teacherSchedules = result.timetable_json?.teacher_schedules || {};
    
    switch (activeTab) {
      case 'classes': {
        const sectionTimetable = timetable[selectedEntity];
        if (!sectionTimetable) return [];
        const flatPeriods: DisplayPeriod[] = [];
        Object.entries(sectionTimetable).forEach(([day, dayPeriods]) => {
          if (Array.isArray(dayPeriods)) {
            dayPeriods.forEach((p) => {
              flatPeriods.push({ ...p, day });
            });
          }
        });
        return flatPeriods;
      }
      case 'teachers': {
        const teacherSchedule = teacherSchedules[selectedEntity];
        if (!teacherSchedule) return [];
        const flatPeriods: DisplayPeriod[] = [];
        Object.entries(teacherSchedule).forEach(([day, dayPeriods]) => {
          if (Array.isArray(dayPeriods)) {
            dayPeriods.forEach((p) => {
              flatPeriods.push({
                period: p.period,
                subject_id: p.subject_id,
                teacher_id: selectedEntity,
                day,
                class_id: p.section_id,
                class_name: p.section_id,
              });
            });
          }
        });
        return flatPeriods;
      }
      case 'resources': {
        // Resource view shows all periods using a specific resource (e.g., Lab, Ground)
        const resourceViews = result.timetable_json?.resource_views || {};
        const resourceView = resourceViews[selectedEntity];
        if (!resourceView) return [];
        const flatPeriods: DisplayPeriod[] = [];
        Object.entries(resourceView).forEach(([day, dayPeriods]) => {
          if (Array.isArray(dayPeriods)) {
            dayPeriods.forEach((p) => {
              flatPeriods.push({
                period: p.period,
                subject_id: p.subject_id,
                teacher_id: p.teacher_id || '',
                day,
                class_id: p.section_id,
                class_name: p.section_id,
                resource_id: selectedEntity,
              });
            });
          }
        });
        return flatPeriods;
      }
      default:
        return [];
    }
  }, [result, selectedEntity, activeTab]);

  // Auto-select first entity when switching tabs
  useMemo(() => {
    if (entities.length > 0 && !entities.includes(selectedEntity)) {
      setSelectedEntity(entities[0]);
    }
  }, [entities, selectedEntity]);

  // Handle period click
  const handlePeriodClick = (period: DisplayPeriod) => {
    setSelectedPeriod(period);
    setEditDialogOpen(true);
  };

  // Handle export
  const handleExport = async (format: 'xlsx' | 'csv' | 'json' | 'pdf') => {
    if (!jobId) return;
    try {
      const blob = await downloadResult(jobId, format, activeTab);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `timetable-${activeTab}-${jobId.slice(0, 8)}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast({
        title: 'Export Complete',
        description: `Downloaded timetable as ${format.toUpperCase()}.`,
      });
    } catch (err) {
      toast({
        title: 'Export Failed',
        description: 'Failed to download the timetable.',
        variant: 'destructive',
      });
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <Loader2 className="h-12 w-12 animate-spin text-primary mx-auto mb-4" />
          <p className="text-muted-foreground">Loading timetable results...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error || !result) {
    return (
      <div className="max-w-4xl mx-auto">
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Failed to Load Results</AlertTitle>
          <AlertDescription>
            {error instanceof Error ? error.message : 'Could not load the timetable results.'}
          </AlertDescription>
        </Alert>
        <div className="flex gap-4 mt-6">
          <Button variant="outline" onClick={() => navigate('/generate')}>
            <ChevronLeft className="h-4 w-4 mr-2" />
            Back to Generate
          </Button>
          <Button onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Retry
          </Button>
        </div>
      </div>
    );
  }

  // Extract data from the nested timetable_json structure
  const gridConfig = result.timetable_json?.grid_config;
  const periodsPerDay = gridConfig?.periods_per_weekday || 8;
  
  // Build period time lookup from grid_config
  const periodTimes: Array<{ start: string; end: string; period: number }> = 
    (gridConfig?.period_times || []).map((pt: { period: number; start_time: string; end_time: string }) => ({
      period: pt.period,
      start: pt.start_time,
      end: pt.end_time,
    }));
  
  // Get break configuration
  const recessAfterPeriods = gridConfig?.recess?.after_periods || [2];
  const lunchAfterPeriod = gridConfig?.lunch?.after_period || 5;
  const prayerEnabled = gridConfig?.prayer_enabled ?? true;
  
  const days = DAYS;
  const solverStatus = result.timetable_json?.status || 'UNKNOWN';
  const isInfeasible = solverStatus === 'INFEASIBLE';
  const hasNoTimetable = !result.timetable_json?.timetable || Object.keys(result.timetable_json.timetable).length === 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Timetable Results</h1>
          <p className="text-muted-foreground mt-1">
            Job {jobId?.slice(0, 8)}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => rerunMutation.mutate()}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Regenerate
          </Button>
        </div>
      </div>

      {/* Status & Diagnostics */}
      {solverStatus !== 'OPTIMAL' && (
        <Alert variant={solverStatus === 'INFEASIBLE' ? 'destructive' : 'default'}>
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>
            {solverStatus === 'INFEASIBLE' ? 'Infeasible Solution' : `Solver Status: ${solverStatus}`}
          </AlertTitle>
          <AlertDescription>
            {solverStatus === 'INFEASIBLE'
              ? 'The solver could not find a valid timetable. Consider relaxing some constraints.'
              : 'A feasible solution was found, but it may not be optimal due to time limits.'}
          </AlertDescription>
        </Alert>
      )}

      {/* Show infeasible help when no timetable generated */}
      {isInfeasible && hasNoTimetable && (
        <Card className="border-destructive/50">
          <CardHeader>
            <CardTitle className="text-base text-destructive">No Timetable Generated</CardTitle>
            <CardDescription>
              The constraints are too strict for the given data. Try the following:
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="list-disc list-inside space-y-2 text-sm text-muted-foreground">
              <li>Disable <strong>Language Block Synchronization</strong> - requires all language teachers free simultaneously</li>
              <li>Disable <strong>Class Teacher Period 1</strong> - may conflict with teacher availability</li>
              <li>Reduce <strong>Substitution Reserve Count</strong> to 0 or 1</li>
              <li>Increase teacher <strong>max_periods_per_day</strong> limits</li>
              <li>Reduce subject <strong>min_per_week</strong> requirements</li>
              <li>Increase the solver <strong>time limit</strong></li>
            </ul>
            <div className="mt-4">
              <Button variant="outline" onClick={() => navigate('/constraints')}>
                <ChevronLeft className="h-4 w-4 mr-2" />
                Back to Constraints
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Diagnostics */}
      {result.diagnostics && result.diagnostics.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Diagnostics</CardTitle>
            <CardDescription>
              Issues and suggestions from the solver
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {result.diagnostics.map((d: Diagnostic, i: number) => (
                <div key={i} className="flex justify-between items-center py-2 border-b last:border-0">
                  <span className="text-sm">{d.message}</span>
                  <span className={cn(
                    "text-xs px-2 py-0.5 rounded",
                    d.type === 'error' && "bg-destructive/10 text-destructive",
                    d.type === 'warning' && "bg-amber-100 text-amber-900",
                    d.type === 'suggestion' && "bg-blue-100 text-blue-900"
                  )}>
                    {d.type}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* View Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <TabsList>
            <TabsTrigger value="classes" className="gap-2">
              <Users className="h-4 w-4" />
              Classes
            </TabsTrigger>
            <TabsTrigger value="teachers" className="gap-2">
              <User className="h-4 w-4" />
              Teachers
            </TabsTrigger>
            {result.timetable_json?.resource_views && Object.keys(result.timetable_json.resource_views).length > 0 && (
              <TabsTrigger value="resources" className="gap-2">
                <Building2 className="h-4 w-4" />
                Resources
              </TabsTrigger>
            )}
          </TabsList>

          {/* Export Options */}
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => handleExport('xlsx')}>
              <FileSpreadsheet className="h-4 w-4 mr-2" />
              Excel
            </Button>
            <Button variant="outline" size="sm" onClick={() => handleExport('csv')}>
              <FileJson className="h-4 w-4 mr-2" />
              CSV
            </Button>
            <Button variant="outline" size="sm" onClick={() => handleExport('pdf')}>
              <Printer className="h-4 w-4 mr-2" />
              PDF
            </Button>
          </div>
        </div>

        {/* Entity Selector */}
        <div className="flex items-center gap-4 mt-4">
          <Label>Select {activeTab === 'classes' ? 'Class' : activeTab === 'teachers' ? 'Teacher' : 'Resource'}:</Label>
          <Select value={selectedEntity} onValueChange={setSelectedEntity}>
            <SelectTrigger className="w-64">
              <SelectValue placeholder={`Select a ${activeTab.slice(0, -1)}`} />
            </SelectTrigger>
            <SelectContent>
              {entities.map((entity) => (
                <SelectItem key={entity} value={entity}>
                  {entity}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {entities.length > 1 && (
            <div className="flex gap-1">
              <Button
                variant="outline"
                size="icon"
                onClick={() => {
                  const idx = entities.indexOf(selectedEntity);
                  if (idx > 0) setSelectedEntity(entities[idx - 1]);
                }}
                disabled={entities.indexOf(selectedEntity) === 0}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="icon"
                onClick={() => {
                  const idx = entities.indexOf(selectedEntity);
                  if (idx < entities.length - 1) setSelectedEntity(entities[idx + 1]);
                }}
                disabled={entities.indexOf(selectedEntity) === entities.length - 1}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}
        </div>

        {/* Timetable Grid */}
        <TabsContent value={activeTab} className="mt-4">
          <Card>
            <CardContent className="p-0 overflow-x-auto">
              <table className="w-full min-w-[800px] border-collapse">
                <thead>
                  <tr className="bg-muted/50">
                    <th className="w-24 p-3 border text-left text-sm font-medium">Time</th>
                    {days.map((day) => (
                      <th key={day} className="p-3 border text-center text-sm font-medium">
                        {DAY_NAMES[day] || day}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {/* Period 0 - Assembly/Prayer (if enabled) */}
                  {prayerEnabled && (
                    <tr className="bg-slate-100">
                      <td className="p-2 border bg-slate-200 text-sm">
                        <div className="font-medium">Assembly</div>
                        <div className="text-xs text-muted-foreground">Period 0</div>
                      </td>
                      {days.map((day) => (
                        <td key={day} className="p-2 border text-center">
                          <div className="text-sm font-medium text-slate-600">
                            🙏 Assembly / Prayer
                          </div>
                        </td>
                      ))}
                    </tr>
                  )}
                  
                  {/* Academic periods with break rows */}
                  {Array.from({ length: periodsPerDay }, (_, periodIdx) => {
                    const periodNum = periodIdx + 1;
                    const time = periodTimes.find(pt => pt.period === periodNum);
                    const isAfterRecess = recessAfterPeriods.includes(periodNum - 1);
                    const isAfterLunch = periodNum === lunchAfterPeriod + 1;
                    
                    const rows = [];
                    
                    // Add Recess row BEFORE this period (if previous period had recess after it)
                    if (isAfterRecess && !isAfterLunch) {
                      rows.push(
                        <tr key={`recess-before-${periodNum}`} className="bg-amber-50">
                          <td className="p-2 border bg-amber-100 text-sm">
                            <div className="font-semibold text-amber-800">RECESS</div>
                            <div className="text-xs text-amber-600">
                              {gridConfig?.recess?.duration_minutes || 20} mins
                            </div>
                          </td>
                          {days.map((day) => (
                            <td key={day} className="p-2 border text-center bg-amber-50">
                              <div className="text-amber-700 font-medium text-sm">☕ BREAK</div>
                            </td>
                          ))}
                        </tr>
                      );
                    }
                    
                    // Add Lunch row BEFORE this period (if previous period had lunch after it)
                    if (isAfterLunch) {
                      rows.push(
                        <tr key={`lunch-before-${periodNum}`} className="bg-green-50">
                          <td className="p-2 border bg-green-100 text-sm">
                            <div className="font-semibold text-green-800">LUNCH</div>
                            <div className="text-xs text-green-600">
                              {gridConfig?.lunch?.duration_minutes || 40} mins
                            </div>
                          </td>
                          {days.map((day) => (
                            <td key={day} className="p-2 border text-center bg-green-50">
                              <div className="text-green-700 font-medium text-sm">🍽️ LUNCH BREAK</div>
                            </td>
                          ))}
                        </tr>
                      );
                    }
                    
                    // Add the academic period row
                    rows.push(
                      <tr key={periodNum}>
                        <td className="p-2 border bg-muted/30 text-sm">
                          <div className="font-medium">Period {periodNum}</div>
                          {time && (
                            <div className="text-xs text-muted-foreground">
                              {formatTime(time.start)} - {formatTime(time.end)}
                            </div>
                          )}
                        </td>
                        {days.map((day) => {
                          const period = periods.find(
                            (p) => p.day === day && p.period === periodNum
                          );
                          return (
                            <td
                              key={day}
                              className={cn(
                                'p-1 border cursor-pointer transition-colors hover:bg-muted/50',
                                !period && 'bg-muted/10'
                              )}
                              onClick={() => period && handlePeriodClick(period)}
                            >
                              {period && (
                                <div
                                  className={cn(
                                    'p-2 rounded border text-xs',
                                    subjectColorMap[period.subject_id]
                                  )}
                                >
                                  <div className="font-medium truncate">
                                    {period.subject_name}
                                  </div>
                                  {activeTab === 'classes' && (
                                    <div className="text-xs opacity-80 truncate">
                                      {period.teacher_name}
                                    </div>
                                  )}
                                  {activeTab === 'teachers' && (
                                    <div className="text-xs opacity-80 truncate">
                                      {period.class_name}
                                    </div>
                                  )}
                                  {period.room_name && (
                                    <div className="text-xs opacity-60 truncate mt-0.5">
                                      📍 {period.room_name}
                                    </div>
                                  )}
                                </div>
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    );
                    
                    return rows;
                  })}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Legend */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Subject Legend</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {Object.entries(subjectColorMap).map(([subjectId, colorClass]) => (
              <div
                key={subjectId}
                className={cn('px-3 py-1 rounded border text-xs font-medium', colorClass)}
              >
                {subjectId}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Edit Period Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Period Details</DialogTitle>
            <DialogDescription>
              View and edit details for this period
            </DialogDescription>
          </DialogHeader>
          {selectedPeriod && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label className="text-muted-foreground">Day</Label>
                  <p className="font-medium">{selectedPeriod.day}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">Period</Label>
                  <p className="font-medium">{selectedPeriod.period}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">Subject</Label>
                  <p className="font-medium">{selectedPeriod.subject_name}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">Teacher</Label>
                  <p className="font-medium">{selectedPeriod.teacher_name}</p>
                </div>
                {selectedPeriod.class_name && (
                  <div>
                    <Label className="text-muted-foreground">Class</Label>
                    <p className="font-medium">{selectedPeriod.class_name}</p>
                  </div>
                )}
                {selectedPeriod.room_name && (
                  <div>
                    <Label className="text-muted-foreground">Room</Label>
                    <p className="font-medium">{selectedPeriod.room_name}</p>
                  </div>
                )}
              </div>
              <Alert>
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>Manual Editing</AlertTitle>
                <AlertDescription>
                  Manual period editing will be available in a future update.
                  For now, regenerate with adjusted constraints.
                </AlertDescription>
              </Alert>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditDialogOpen(false)}>
              <X className="h-4 w-4 mr-2" />
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Navigation */}
      <div className="flex justify-between">
        <Button variant="outline" onClick={() => navigate('/generate')}>
          <ChevronLeft className="h-4 w-4 mr-2" />
          Back to Generate
        </Button>
        <Button variant="outline" onClick={() => navigate('/jobs')}>
          View All Jobs
          <ChevronRight className="h-4 w-4 ml-2" />
        </Button>
      </div>
    </div>
  );
}
