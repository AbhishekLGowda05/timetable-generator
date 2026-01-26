import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import {
  Settings2,
  ChevronRight,
  ChevronLeft,
  Info,
  Save,
  RefreshCw,
  Clock,
  Users,
  BookOpen,
  Building2,
  X,
  MonitorSmartphone,
  Loader2,
  Database,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Slider } from '@/components/ui/slider';
import { useToast } from '@/components/ui/use-toast';
import { useConstraintsStore, useUploadStore } from '@/stores';
import { ConstraintsSchema, type Constraints, type Teacher, type Resource, type Subject, type Weekday } from '@/lib/schemas';
import { get } from '@/lib/api-client';

// Constraint definitions with descriptions
const hardConstraints = [
  {
    key: 'language_sync_enabled',
    label: 'Language Block Synchronization',
    description: 'All language teachers for a section must be free during language periods.',
    example: 'If Hindi, Kannada, and Sanskrit are taught, all three teachers must be free simultaneously.',
    warning: '⚠️ May cause infeasibility with many sections - use only if your school uses language blocks.',
  },
  {
    key: 'class_teacher_period_1',
    label: 'Class Teacher in Period 1',
    description: 'Class teacher must have Period 1 with their assigned section.',
    example: 'Mrs. Sharma (class teacher of 8A) will always have Period 1 with 8A for attendance.',
    warning: '⚠️ May conflict with teacher availability constraints.',
  },
  {
    key: 'no_subject_twice_daily',
    label: 'No Subject Twice Daily',
    description: 'Prevent the same subject from appearing twice on the same day (except lab blocks).',
    example: 'Math won\'t appear in both P2 and P6 on Monday.',
  },
  {
    key: 'core_morning_only',
    label: 'Core Subjects in Morning',
    description: 'Schedule core subjects (Math, Science, English) before lunch.',
    example: 'Mathematics will be scheduled in P1-P4 instead of P5-P7.',
    warning: '⚠️ Hard constraint - may reduce solution space significantly.',
  },
  {
    key: 'subject_frequency_enabled',
    label: 'Subject Frequency Bounds',
    description: 'Enforce min/max periods per week for each subject.',
    example: 'Math must have 6-7 periods per week, PE must have exactly 2.',
  },
  {
    key: 'teacher_load_bounds_enabled',
    label: 'Teacher Load Bounds',
    description: 'Enforce min/max periods per day and week for teachers.',
    example: 'Teacher cannot exceed 6 periods/day or 30 periods/week.',
  },
  {
    key: 'block_period_integrity',
    label: 'Block Period Integrity',
    description: 'Lab sessions must have consecutive periods and cannot bridge breaks.',
    example: 'Physics Lab (2 periods) must be P3-P4, not P3-Recess-P5.',
  },
  {
    key: 'resource_capacity_enabled',
    label: 'Resource Capacity Limits',
    description: 'Enforce max simultaneous usage of labs, grounds, etc.',
    example: 'Only 2 sections can use Computer Lab simultaneously.',
  },
];

const softWeightDescriptions: Record<string, { label: string; description: string; scale: string }> = {
  teacher_balance: {
    label: 'Teacher Load Balance',
    description: 'Distribute teaching hours evenly across the week.',
    scale: 'Higher = more balanced distribution',
  },
  minimize_gaps: {
    label: 'Minimize Idle Gaps',
    description: 'Reduce free periods between classes for teachers.',
    scale: 'Higher = fewer gaps in teacher schedules',
  },
  core_morning: {
    label: 'Core Morning Preference',
    description: 'Weight for scheduling core subjects in morning.',
    scale: 'Higher = core subjects more likely before lunch',
  },
  leisure_afternoon: {
    label: 'Leisure Afternoon',
    description: 'Schedule PE, Art, Music in afternoon slots.',
    scale: 'Higher = leisure subjects more likely after lunch',
  },
  avoid_pe_period_1: {
    label: 'Avoid PE in Period 1',
    description: 'Students may not be physically ready early morning.',
    scale: 'Higher = PE less likely in first period',
  },
  avoid_pe_after_lunch: {
    label: 'Avoid PE After Lunch',
    description: 'Give students time to digest before physical activity.',
    scale: 'Higher = PE less likely immediately after lunch',
  },
  subject_distribution: {
    label: 'Subject Distribution',
    description: 'Spread heavy subjects across the week.',
    scale: 'Higher = more evenly spread subjects',
  },
  teacher_free_period: {
    label: 'Teacher Free Period',
    description: 'Ensure teachers get at least one free period daily.',
    scale: 'Higher = stronger preference for daily free periods',
  },
  fair_slot_distribution: {
    label: 'Fair Slot Distribution',
    description: 'Distribute undesirable slots (last period, Friday) fairly.',
    scale: 'Higher = more equitable bad slot assignments',
  },
  specialist_priority: {
    label: 'Specialist Priority',
    description: 'Prioritize scheduling specialist/part-time teachers first.',
    scale: 'Higher = specialist slots locked in earlier',
  },
  thinking_break_math: {
    label: 'Math Thinking Break',
    description: 'Avoid consecutive math periods on the same day.',
    scale: 'Higher = more gap between math sessions',
  },
  language_spread: {
    label: 'Language Spread',
    description: 'Avoid language subjects on same day as language block.',
    scale: 'Higher = better language distribution',
  },
  saturday_monday_balance: {
    label: 'Saturday-Monday Balance',
    description: 'If teacher works full Saturday, give lighter Monday.',
    scale: 'Higher = stronger weekend balance',
  },
};

export function ConstraintsPage() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { uploadId, teachers, subjects, classes, resources, setUploadId, setPreview, setSchool, setTeachers, setSubjects, setClasses, setResources } = useUploadStore();
  const { constraints, setConstraints, resetConstraints, isDirty, markClean } = useConstraintsStore();
  const [activeTab, setActiveTab] = useState('grid');
  
  // Teacher Availability Modal State
  const [selectedTeacher, setSelectedTeacher] = useState<Teacher | null>(null);
  const [teacherAvailabilityModal, setTeacherAvailabilityModal] = useState(false);
  const [editingAvailability, setEditingAvailability] = useState<Record<string, { available: boolean; blocked_periods: number[] }>>({});
  
  // Resource Configuration State  
  const [resourceConfigModal, setResourceConfigModal] = useState(false);
  const [selectedResource, setSelectedResource] = useState<Resource | null>(null);
  const [editingResourceCapacity, setEditingResourceCapacity] = useState(1);

  // Subject Time Restriction Modal State
  const [subjectModal, setSubjectModal] = useState(false);
  const [selectedSubject, setSelectedSubject] = useState<Subject | null>(null);
  const [editingSubjectAllowedDays, setEditingSubjectAllowedDays] = useState<Weekday[]>([]);
  const [editingSubjectAllowedPeriods, setEditingSubjectAllowedPeriods] = useState<number[]>([]);

  const weekdays: Weekday[] = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const periods = useMemo(() => Array.from({ length: constraints.periods_per_weekday }, (_, i) => i + 1), [constraints.periods_per_weekday]);

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
        description: 'Vidya Mandir High School sample data is ready. You can now configure overrides.',
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

  const {
    control,
    handleSubmit,
    reset,
  } = useForm<Constraints>({
    resolver: zodResolver(ConstraintsSchema),
    defaultValues: constraints,
  });

  const onSubmit = (data: Constraints) => {
    setConstraints(data);
    markClean();
    toast({
      title: 'Constraints Saved',
      description: 'Your constraint settings have been saved.',
    });
  };

  const handleReset = () => {
    resetConstraints();
    reset(ConstraintsSchema.parse({}));
    toast({
      title: 'Constraints Reset',
      description: 'All constraints have been reset to defaults.',
    });
  };

  const handleContinue = () => {
    if (!uploadId) {
      toast({
        title: 'No Data Uploaded',
        description: 'Please upload your school data first.',
        variant: 'destructive',
      });
      navigate('/upload');
      return;
    }
    navigate('/generate');
  };

  // Open teacher availability modal
  const openTeacherModal = (teacher: Teacher) => {
    setSelectedTeacher(teacher);
    // Initialize availability state from teacher data
    const availability: Record<string, { available: boolean; blocked_periods: number[] }> = {};
    weekdays.forEach(day => {
      const existingAvail = teacher.availability?.[day];
      availability[day] = {
        available: existingAvail?.available ?? true,
        blocked_periods: existingAvail?.blocked_periods ?? [],
      };
    });
    setEditingAvailability(availability);
    setTeacherAvailabilityModal(true);
  };

  // Toggle day availability
  const toggleDayAvailability = (day: string) => {
    setEditingAvailability(prev => ({
      ...prev,
      [day]: {
        ...prev[day],
        available: !prev[day].available,
        blocked_periods: !prev[day].available ? [] : prev[day].blocked_periods,
      }
    }));
  };

  // Toggle period blocked
  const togglePeriodBlocked = (day: string, period: number) => {
    setEditingAvailability(prev => {
      const current = prev[day].blocked_periods || [];
      const isBlocked = current.includes(period);
      return {
        ...prev,
        [day]: {
          ...prev[day],
          blocked_periods: isBlocked 
            ? current.filter(p => p !== period)
            : [...current, period].sort((a, b) => a - b),
        }
      };
    });
  };

  // Save teacher availability
  const saveTeacherAvailability = () => {
    if (!selectedTeacher) return;
    
    const updatedTeachers = teachers.map(t => {
      if (t.teacher_id === selectedTeacher.teacher_id) {
        return {
          ...t,
          availability: editingAvailability,
        };
      }
      return t;
    });
    
    setTeachers(updatedTeachers);
    setTeacherAvailabilityModal(false);
    setSelectedTeacher(null);
    toast({
      title: 'Availability Updated',
      description: `${selectedTeacher.name}'s availability has been saved.`,
    });
  };

  // Open resource config modal
  const openResourceModal = (resource: Resource) => {
    setSelectedResource(resource);
    setEditingResourceCapacity(resource.max_simultaneous_capacity);
    setResourceConfigModal(true);
  };

  // Save resource configuration
  const saveResourceConfig = () => {
    if (!selectedResource) return;
    
    const updatedResources = resources.map(r => {
      if (r.resource_id === selectedResource.resource_id) {
        return {
          ...r,
          max_simultaneous_capacity: editingResourceCapacity,
        };
      }
      return r;
    });
    
    setResources(updatedResources);
    setResourceConfigModal(false);
    setSelectedResource(null);
    toast({
      title: 'Resource Updated',
      description: `${selectedResource.name || selectedResource.resource_id} configuration saved.`,
    });
  };

  // Open subject time restriction modal
  const openSubjectModal = (subject: Subject) => {
    setSelectedSubject(subject);
    // Initialize from existing restrictions or default to all days/periods
    const restriction = subject.time_restriction;
    setEditingSubjectAllowedDays(restriction?.allowed_days ?? [...weekdays]);
    setEditingSubjectAllowedPeriods(restriction?.allowed_periods ?? [...periods]);
    setSubjectModal(true);
  };

  // Toggle day in subject allowed days
  const toggleSubjectDay = (day: Weekday) => {
    setEditingSubjectAllowedDays(prev => 
      prev.includes(day) 
        ? prev.filter(d => d !== day)
        : [...prev, day]
    );
  };

  // Toggle period in subject allowed periods
  const toggleSubjectPeriod = (period: number) => {
    setEditingSubjectAllowedPeriods(prev =>
      prev.includes(period)
        ? prev.filter(p => p !== period)
        : [...prev, period].sort((a, b) => a - b)
    );
  };

  // Save subject time restriction
  const saveSubjectRestriction = () => {
    if (!selectedSubject) return;
    
    const isAllDays = editingSubjectAllowedDays.length === weekdays.length;
    const isAllPeriods = editingSubjectAllowedPeriods.length === periods.length;
    
    const updatedSubjects = subjects.map(s => {
      if (s.subject_id === selectedSubject.subject_id) {
        return {
          ...s,
          time_restriction: (isAllDays && isAllPeriods) ? undefined : {
            allowed_days: isAllDays ? undefined : editingSubjectAllowedDays,
            allowed_periods: isAllPeriods ? undefined : editingSubjectAllowedPeriods,
          },
        };
      }
      return s;
    });
    
    setSubjects(updatedSubjects);
    setSubjectModal(false);
    setSelectedSubject(null);
    toast({
      title: 'Subject Restriction Updated',
      description: `${selectedSubject.name}'s time restrictions have been saved.`,
    });
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Configure Constraints</h1>
          <p className="text-muted-foreground mt-2">
            Set up scheduling rules and preferences for the timetable generator.
          </p>
        </div>
        {isDirty && (
          <span className="text-sm text-warning">Unsaved changes</span>
        )}
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="grid" className="flex items-center gap-2">
            <Clock className="h-4 w-4" />
            Grid Timing
          </TabsTrigger>
          <TabsTrigger value="hard" className="flex items-center gap-2">
            <Settings2 className="h-4 w-4" />
            Hard Constraints
          </TabsTrigger>
          <TabsTrigger value="soft" className="flex items-center gap-2">
            <BookOpen className="h-4 w-4" />
            Soft Weights
          </TabsTrigger>
          <TabsTrigger value="overrides" className="flex items-center gap-2">
            <Users className="h-4 w-4" />
            Overrides
          </TabsTrigger>
          <TabsTrigger value="solver" className="flex items-center gap-2">
            <MonitorSmartphone className="h-4 w-4" />
            Solver
          </TabsTrigger>
        </TabsList>

        {/* Grid Timing Tab */}
        <TabsContent value="grid">
          <Card>
            <CardHeader>
              <CardTitle>School Time Grid</CardTitle>
              <CardDescription>
                Configure the basic timing structure for your school.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-8">
              {/* School Timing Section */}
              <div className="space-y-4">
                <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                  School Timing
                </h3>
                <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
                  <div className="space-y-2">
                    <Label htmlFor="school_start_time">Start Time</Label>
                    <Controller
                      name="school_start_time"
                      control={control}
                      render={({ field }) => (
                        <Input
                          type="time"
                          {...field}
                        />
                      )}
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="school_end_time">End Time</Label>
                    <Controller
                      name="school_end_time"
                      control={control}
                      render={({ field }) => (
                        <Input
                          type="time"
                          {...field}
                        />
                      )}
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="periods_per_weekday">Periods per Weekday</Label>
                    <Controller
                      name="periods_per_weekday"
                      control={control}
                      render={({ field }) => (
                        <Select
                          value={String(field.value)}
                          onValueChange={(v) => field.onChange(parseInt(v))}
                        >
                          <SelectTrigger>
                            <SelectValue placeholder="Select periods" />
                          </SelectTrigger>
                          <SelectContent>
                            {[6, 7, 8, 9, 10, 11, 12].map((n) => (
                              <SelectItem key={n} value={String(n)}>
                                {n} periods
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      )}
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="period_duration_minutes">Period Duration</Label>
                    <Controller
                      name="period_duration_minutes"
                      control={control}
                      render={({ field }) => (
                        <Select
                          value={String(field.value)}
                          onValueChange={(v) => field.onChange(parseInt(v))}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {[30, 35, 40, 45, 50, 55, 60].map((n) => (
                              <SelectItem key={n} value={String(n)}>
                                {n} minutes
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      )}
                    />
                  </div>
                </div>
              </div>
              
              {/* Assembly/Prayer Section */}
              <div className="space-y-4">
                <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                  Assembly/Prayer (Period 0)
                </h3>
                <div className="grid gap-6 md:grid-cols-2">
                  <div className="flex items-center justify-between p-4 border rounded-lg">
                    <div className="space-y-1">
                      <Label htmlFor="prayer_enabled" className="font-medium">
                        Enable Period 0
                      </Label>
                      <p className="text-sm text-muted-foreground">
                        Reserve first period for assembly/prayer
                      </p>
                    </div>
                    <Controller
                      name="prayer_enabled"
                      control={control}
                      render={({ field }) => (
                        <Switch
                          id="prayer_enabled"
                          checked={field.value}
                          onCheckedChange={field.onChange}
                        />
                      )}
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="prayer_duration_minutes">Assembly Duration</Label>
                    <Controller
                      name="prayer_duration_minutes"
                      control={control}
                      render={({ field }) => (
                        <Select
                          value={String(field.value)}
                          onValueChange={(v) => field.onChange(parseInt(v))}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {[15, 20, 25, 30, 35, 40, 45].map((n) => (
                              <SelectItem key={n} value={String(n)}>
                                {n} minutes
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      )}
                    />
                  </div>
                </div>
              </div>
              
              {/* Breaks Section */}
              <div className="space-y-4">
                <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                  Breaks
                </h3>
                <div className="grid gap-6 md:grid-cols-2">
                  <div className="p-4 border rounded-lg space-y-4">
                    <h4 className="font-medium">Recess</h4>
                    <div className="grid gap-4 grid-cols-2">
                      <div className="space-y-2">
                        <Label htmlFor="recess_after_period">After Period</Label>
                        <Controller
                          name="recess_after_period"
                          control={control}
                          render={({ field }) => (
                            <Select
                              value={String(field.value)}
                              onValueChange={(v) => field.onChange(parseInt(v))}
                            >
                              <SelectTrigger>
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                {[1, 2, 3, 4, 5].map((n) => (
                                  <SelectItem key={n} value={String(n)}>
                                    Period {n}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          )}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="recess_duration_minutes">Duration</Label>
                        <Controller
                          name="recess_duration_minutes"
                          control={control}
                          render={({ field }) => (
                            <Select
                              value={String(field.value)}
                              onValueChange={(v) => field.onChange(parseInt(v))}
                            >
                              <SelectTrigger>
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                {[10, 15, 20, 25, 30].map((n) => (
                                  <SelectItem key={n} value={String(n)}>
                                    {n} mins
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          )}
                        />
                      </div>
                    </div>
                  </div>
                  
                  <div className="p-4 border rounded-lg space-y-4">
                    <h4 className="font-medium">Lunch</h4>
                    <div className="grid gap-4 grid-cols-2">
                      <div className="space-y-2">
                        <Label htmlFor="lunch_after_period">After Period</Label>
                        <Controller
                          name="lunch_after_period"
                          control={control}
                          render={({ field }) => (
                            <Select
                              value={String(field.value)}
                              onValueChange={(v) => field.onChange(parseInt(v))}
                            >
                              <SelectTrigger>
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                {[3, 4, 5, 6, 7].map((n) => (
                                  <SelectItem key={n} value={String(n)}>
                                    Period {n}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          )}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="lunch_duration_minutes">Duration</Label>
                        <Controller
                          name="lunch_duration_minutes"
                          control={control}
                          render={({ field }) => (
                            <Select
                              value={String(field.value)}
                              onValueChange={(v) => field.onChange(parseInt(v))}
                            >
                              <SelectTrigger>
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                {[20, 30, 40, 45, 50, 60].map((n) => (
                                  <SelectItem key={n} value={String(n)}>
                                    {n} mins
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          )}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              
              {/* Saturday & Other Settings */}
              <div className="space-y-4">
                <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                  Saturday & Other Settings
                </h3>
                <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
                  <div className="space-y-2">
                    <Label htmlFor="saturday_periods">Saturday Periods</Label>
                    <Controller
                      name="saturday_periods"
                      control={control}
                      render={({ field }) => (
                        <Select
                          value={String(field.value)}
                          onValueChange={(v) => field.onChange(parseInt(v))}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="0">No Saturday</SelectItem>
                            {[2, 3, 4, 5, 6].map((n) => (
                              <SelectItem key={n} value={String(n)}>
                                {n} periods
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      )}
                    />
                    <p className="text-xs text-muted-foreground">
                      Half-day on Saturday
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="substitution_reserve_count">Substitution Reserve</Label>
                    <Controller
                      name="substitution_reserve_count"
                      control={control}
                      render={({ field }) => (
                        <Input
                          type="number"
                          min={0}
                          max={10}
                          {...field}
                          onChange={(e) => field.onChange(parseInt(e.target.value) || 0)}
                        />
                      )}
                    />
                    <p className="text-xs text-muted-foreground">
                      Free teachers per period for emergencies
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="max_consecutive_default">Max Consecutive Periods</Label>
                    <Controller
                      name="max_consecutive_default"
                      control={control}
                      render={({ field }) => (
                        <Select
                          value={String(field.value)}
                          onValueChange={(v) => field.onChange(parseInt(v))}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {[2, 3, 4, 5].map((n) => (
                              <SelectItem key={n} value={String(n)}>
                                {n} periods
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      )}
                    />
                    <p className="text-xs text-muted-foreground">
                      Before a break is required
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="max_daily_load_variance">Max Daily Load Variance</Label>
                    <Controller
                      name="max_daily_load_variance"
                      control={control}
                      render={({ field }) => (
                        <Select
                          value={String(field.value)}
                          onValueChange={(v) => field.onChange(parseInt(v))}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {[1, 2, 3, 4, 5].map((n) => (
                              <SelectItem key={n} value={String(n)}>
                                ±{n} periods
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      )}
                    />
                    <p className="text-xs text-muted-foreground">
                      Difference between busiest and lightest day
                    </p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Hard Constraints Tab */}
        <TabsContent value="hard">
          <Card>
            <CardHeader>
              <CardTitle>Hard Constraints</CardTitle>
              <CardDescription>
                These rules must be satisfied. The solver will fail if any are violated.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {hardConstraints.map((constraint) => (
                <div
                  key={constraint.key}
                  className="flex items-start justify-between p-4 border rounded-lg"
                >
                  <div className="flex-1 space-y-1">
                    <div className="flex items-center gap-2">
                      <Label htmlFor={constraint.key} className="font-medium">
                        {constraint.label}
                      </Label>
                      <Tooltip>
                        <TooltipTrigger>
                          <Info className="h-4 w-4 text-muted-foreground" />
                        </TooltipTrigger>
                        <TooltipContent className="max-w-xs">
                          <p className="font-medium mb-1">{constraint.description}</p>
                          <p className="text-xs text-muted-foreground">
                            Example: {constraint.example}
                          </p>
                        </TooltipContent>
                      </Tooltip>
                    </div>
                    <p className="text-sm text-muted-foreground">{constraint.description}</p>
                  </div>
                  <Controller
                    name={constraint.key as keyof Constraints}
                    control={control}
                    render={({ field }) => (
                      <Switch
                        id={constraint.key}
                        checked={field.value as boolean}
                        onCheckedChange={field.onChange}
                      />
                    )}
                  />
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Soft Weights Tab */}
        <TabsContent value="soft">
          <Card>
            <CardHeader>
              <CardTitle>Soft Constraint Weights</CardTitle>
              <CardDescription>
                Adjust the importance of each preference. Higher values = stronger preference.
                Set to 0 to disable. Hover over the info icon for scale explanation.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-2">
                {Object.entries(softWeightDescriptions).map(([key, { label, description, scale }]) => (
                  <div key={key} className="space-y-3 p-4 border rounded-lg">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Label htmlFor={`soft_weights.${key}`} className="font-medium">
                          {label}
                        </Label>
                        <Tooltip>
                          <TooltipTrigger>
                            <Info className="h-4 w-4 text-muted-foreground" />
                          </TooltipTrigger>
                          <TooltipContent className="max-w-xs">
                            <p className="font-medium mb-1">Scale Guide:</p>
                            <p className="text-xs">{scale}</p>
                          </TooltipContent>
                        </Tooltip>
                      </div>
                      <Controller
                        name={`soft_weights.${key}` as `soft_weights.${keyof Constraints['soft_weights']}`}
                        control={control}
                        render={({ field }) => (
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-mono w-6 text-center">{field.value}</span>
                          </div>
                        )}
                      />
                    </div>
                    <Controller
                      name={`soft_weights.${key}` as `soft_weights.${keyof Constraints['soft_weights']}`}
                      control={control}
                      render={({ field }) => (
                        <Slider
                          value={[field.value]}
                          onValueChange={(vals) => field.onChange(vals[0])}
                          min={0}
                          max={20}
                          step={1}
                          className="w-full"
                        />
                      )}
                    />
                    <div className="flex justify-between text-[10px] text-muted-foreground">
                      <span>Disabled (0)</span>
                      <span>Moderate (10)</span>
                      <span>Critical (20)</span>
                    </div>
                    <p className="text-xs text-muted-foreground">{description}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Overrides Tab */}
        <TabsContent value="overrides">
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Teacher Overrides */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Users className="h-5 w-5" />
                  Teacher Availability Overrides
                </CardTitle>
                <CardDescription>
                  Set individual availability and blocked periods per teacher.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {teachers.length > 0 ? (
                  <div className="space-y-2 max-h-80 overflow-y-auto">
                    {teachers.map((teacher) => {
                      const hasCustomAvail = teacher.availability && Object.keys(teacher.availability).length > 0;
                      const blockedCount = hasCustomAvail 
                        ? Object.values(teacher.availability!).reduce((sum, a) => sum + (a.blocked_periods?.length || 0), 0)
                        : 0;
                      return (
                        <div
                          key={teacher.teacher_id}
                          className="flex items-center justify-between p-3 border rounded-lg hover:bg-muted/50 cursor-pointer"
                          onClick={() => openTeacherModal(teacher)}
                        >
                          <div className="flex-1">
                            <p className="font-medium">{teacher.name}</p>
                            <p className="text-xs text-muted-foreground">
                              {teacher.subjects_can_teach.slice(0, 3).join(', ')}
                              {teacher.subjects_can_teach.length > 3 && '...'}
                            </p>
                            {hasCustomAvail && (
                              <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">
                                {blockedCount} periods blocked
                              </p>
                            )}
                          </div>
                          <Button variant="ghost" size="sm" onClick={(e) => { e.stopPropagation(); openTeacherModal(teacher); }}>
                            Edit
                          </Button>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="text-center py-8 space-y-4">
                    <p className="text-muted-foreground">
                      Upload data to configure teacher overrides.
                    </p>
                    <Button 
                      variant="outline" 
                      onClick={() => loadSampleDataMutation.mutate()}
                      disabled={loadSampleDataMutation.isPending}
                    >
                      {loadSampleDataMutation.isPending ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          Loading...
                        </>
                      ) : (
                        <>
                          <Database className="h-4 w-4 mr-2" />
                          Load Sample Data
                        </>
                      )}
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Class Overrides */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Building2 className="h-5 w-5" />
                  Class Overrides
                </CardTitle>
                <CardDescription>
                  Configure language blocks and subject mappings per class.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {classes.length > 0 ? (
                  <div className="space-y-2 max-h-80 overflow-y-auto">
                    {classes.map((cls) => (
                      <div
                        key={cls.section_id}
                        className="flex items-center justify-between p-3 border rounded-lg hover:bg-muted/50 cursor-pointer"
                      >
                        <div>
                          <p className="font-medium">Grade {cls.grade} - {cls.section_name}</p>
                          <p className="text-xs text-muted-foreground">
                            {Object.keys(cls.subject_teacher_map).length} subjects
                          </p>
                          {cls.language_block_enabled && (
                            <p className="text-xs text-blue-600 dark:text-blue-400 mt-1">
                              Language block enabled
                            </p>
                          )}
                        </div>
                        <Button variant="ghost" size="sm">
                          Edit
                        </Button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 space-y-4">
                    <p className="text-muted-foreground">
                      Upload data to configure class overrides.
                    </p>
                    <Button 
                      variant="outline" 
                      onClick={() => loadSampleDataMutation.mutate()}
                      disabled={loadSampleDataMutation.isPending}
                    >
                      {loadSampleDataMutation.isPending ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          Loading...
                        </>
                      ) : (
                        <>
                          <Database className="h-4 w-4 mr-2" />
                          Load Sample Data
                        </>
                      )}
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Subject Time Restrictions */}
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BookOpen className="h-5 w-5" />
                  Subject Time Restrictions
                </CardTitle>
                <CardDescription>
                  Configure when specific subjects can be scheduled (e.g., Yoga only Mon-Wed 9-12am).
                </CardDescription>
              </CardHeader>
              <CardContent>
                {subjects.length > 0 ? (
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {subjects.map((subject) => {
                      const hasRestriction = subject.time_restriction && 
                        (subject.time_restriction.allowed_days?.length || 
                         subject.time_restriction.allowed_periods?.length ||
                         subject.time_restriction.blocked_days?.length ||
                         subject.time_restriction.blocked_periods?.length);
                      return (
                        <div
                          key={subject.subject_id}
                          className="p-4 border rounded-lg space-y-2 hover:bg-muted/50 cursor-pointer"
                          onClick={() => openSubjectModal(subject)}
                        >
                          <div className="flex items-center justify-between">
                            <p className="font-medium">{subject.name}</p>
                            <span className="px-2 py-1 text-xs bg-secondary rounded">
                              {subject.category}
                            </span>
                          </div>
                          <p className="text-xs text-muted-foreground">
                            {subject.min_per_week}-{subject.max_per_week} periods/week
                          </p>
                          {hasRestriction && (
                            <p className="text-xs text-amber-600 dark:text-amber-400">
                              Custom time restrictions applied
                            </p>
                          )}
                          {subject.prefer_morning && (
                            <p className="text-xs text-blue-600 dark:text-blue-400">
                              Prefers morning slots
                            </p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="text-center py-8 space-y-4">
                    <p className="text-muted-foreground">
                      Upload data to configure subject time restrictions.
                    </p>
                    <Button 
                      variant="outline" 
                      onClick={() => loadSampleDataMutation.mutate()}
                      disabled={loadSampleDataMutation.isPending}
                    >
                      {loadSampleDataMutation.isPending ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          Loading...
                        </>
                      ) : (
                        <>
                          <Database className="h-4 w-4 mr-2" />
                          Load Sample Data
                        </>
                      )}
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Resource Configuration */}
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <MonitorSmartphone className="h-5 w-5" />
                  Resource Configuration
                </CardTitle>
                <CardDescription>
                  Configure labs, grounds, and other shared resources with capacity limits.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {resources.length > 0 ? (
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {resources.map((resource) => (
                      <div
                        key={resource.resource_id}
                        className="p-4 border rounded-lg space-y-2 hover:bg-muted/50 cursor-pointer"
                        onClick={() => openResourceModal(resource)}
                      >
                        <div className="flex items-center justify-between">
                          <p className="font-medium">{resource.name || resource.resource_id}</p>
                          <span className="px-2 py-1 text-xs bg-secondary rounded">
                            {resource.resource_type}
                          </span>
                        </div>
                        <p className="text-sm text-muted-foreground">
                          Max capacity: {resource.max_simultaneous_capacity} sections
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 space-y-4">
                    <p className="text-muted-foreground">
                      No resources uploaded. Add resources (labs, grounds, etc.) in the Upload step.
                    </p>
                    <Button 
                      variant="outline" 
                      onClick={() => loadSampleDataMutation.mutate()}
                      disabled={loadSampleDataMutation.isPending}
                    >
                      {loadSampleDataMutation.isPending ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          Loading...
                        </>
                      ) : (
                        <>
                          <Database className="h-4 w-4 mr-2" />
                          Load Sample Data
                        </>
                      )}
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Solver Configuration Tab */}
        <TabsContent value="solver">
          <Card>
            <CardHeader>
              <CardTitle>Solver Configuration</CardTitle>
              <CardDescription>
                Configure how the timetable generator runs. These settings affect solution quality and time.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-8">
              {/* Solver Mode */}
              <div className="space-y-4">
                <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                  Solver Mode
                </h3>
                <div className="p-4 border rounded-lg bg-primary/5">
                  <div className="flex items-start gap-4">
                    <div className="p-2 rounded-full bg-primary/10">
                      <MonitorSmartphone className="h-6 w-6 text-primary" />
                    </div>
                    <div className="flex-1 space-y-1">
                      <p className="font-medium text-primary">Demo Mode Active</p>
                      <p className="text-sm text-muted-foreground">
                        In demo mode, jobs are processed immediately with extended time limits for better optimization.
                        The solver will use up to <strong>120 seconds</strong> to find the best possible timetable.
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Time Allocation */}
              <div className="space-y-4">
                <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                  Time Allocation
                </h3>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="p-4 border rounded-lg space-y-2">
                    <div className="flex items-center gap-2">
                      <Clock className="h-5 w-5 text-muted-foreground" />
                      <span className="font-medium">Default Time Limit</span>
                    </div>
                    <p className="text-2xl font-bold text-primary">120 seconds</p>
                    <p className="text-sm text-muted-foreground">
                      The solver will run for up to 2 minutes to find the optimal solution.
                      More time generally means better quality results.
                    </p>
                  </div>
                  
                  <div className="p-4 border rounded-lg space-y-2">
                    <div className="flex items-center gap-2">
                      <RefreshCw className="h-5 w-5 text-muted-foreground" />
                      <span className="font-medium">Parallel Workers</span>
                    </div>
                    <p className="text-2xl font-bold text-primary">8 workers</p>
                    <p className="text-sm text-muted-foreground">
                      Multiple parallel search workers explore the solution space simultaneously
                      for better optimization.
                    </p>
                  </div>
                </div>
              </div>

              {/* Staffing Guidelines */}
              <div className="space-y-4">
                <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                  Staffing Guidelines (India School Standards)
                </h3>
                <div className="grid gap-4 md:grid-cols-3">
                  <div className="p-4 border rounded-lg">
                    <p className="font-medium">Teacher-to-Class Ratio</p>
                    <p className="text-xl font-bold text-primary">1.5 : 1</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      1.5 teachers per section (40-45 periods/week ÷ 28-30 teaching capacity)
                    </p>
                  </div>
                  <div className="p-4 border rounded-lg">
                    <p className="font-medium">Subject Coverage</p>
                    <p className="text-xl font-bold text-primary">1 : 3.5</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      One specialist teacher covers ~3-4 sections of their subject
                    </p>
                  </div>
                  <div className="p-4 border rounded-lg">
                    <p className="font-medium">Max Teacher Load</p>
                    <p className="text-xl font-bold text-primary">26-30</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      Periods per week (leaving time for corrections & planning)
                    </p>
                  </div>
                </div>
              </div>

              {/* Solver Tips */}
              <div className="space-y-4">
                <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                  Optimization Tips
                </h3>
                <div className="p-4 border rounded-lg bg-muted/30 space-y-3">
                  <div className="flex items-start gap-3">
                    <Info className="h-5 w-5 text-blue-500 mt-0.5" />
                    <div>
                      <p className="font-medium">Start with fewer hard constraints</p>
                      <p className="text-sm text-muted-foreground">
                        If getting infeasible results, disable Language Block Synchronization and 
                        Class Teacher Period 1 first. These are the most restrictive.
                      </p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <Info className="h-5 w-5 text-green-500 mt-0.5" />
                    <div>
                      <p className="font-medium">Use soft constraints for preferences</p>
                      <p className="text-sm text-muted-foreground">
                        &quot;Core subjects in morning&quot; works better as a soft preference (weighted)
                        than as a hard constraint that must be satisfied.
                      </p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <Info className="h-5 w-5 text-amber-500 mt-0.5" />
                    <div>
                      <p className="font-medium">Check teacher availability</p>
                      <p className="text-sm text-muted-foreground">
                        Ensure teachers have enough available periods to cover their assigned sections.
                        A teacher with max 6 periods/day can&apos;t teach 8 sections requiring 40 periods/week.
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Deadline Scheduling (Future Feature) */}
              <div className="space-y-4">
                <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
                  Deadline Scheduling
                  <span className="px-2 py-0.5 text-xs bg-secondary rounded">Coming Soon</span>
                </h3>
                <div className="p-4 border rounded-lg border-dashed opacity-70">
                  <p className="text-sm text-muted-foreground">
                    <strong>Scheduled Generation:</strong> In production mode, you&apos;ll be able to submit 
                    constraints in the morning (e.g., 9 AM) and schedule results to be ready by a specific 
                    time (e.g., 3 PM). The system will automatically allocate optimal solver time based on 
                    server availability and queue depth.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Teacher Availability Modal */}
      <Dialog open={teacherAvailabilityModal} onOpenChange={setTeacherAvailabilityModal}>
        <DialogContent className="sm:max-w-[700px]">
          <DialogHeader>
            <DialogTitle>Edit Availability: {selectedTeacher?.name}</DialogTitle>
            <DialogDescription>
              Toggle days on/off and click individual periods to block them.
              Blocked periods will not be assigned to this teacher.
            </DialogDescription>
          </DialogHeader>
          
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr>
                  <th className="p-2 text-left font-medium text-sm">Day</th>
                  <th className="p-2 text-center font-medium text-sm">Available</th>
                  {periods.map(p => (
                    <th key={p} className="p-2 text-center font-medium text-sm">P{p}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {weekdays.map(day => {
                  const dayAvail = editingAvailability[day];
                  const isAvailable = dayAvail?.available ?? true;
                  return (
                    <tr key={day} className={!isAvailable ? 'opacity-50' : ''}>
                      <td className="p-2 font-medium">{day}</td>
                      <td className="p-2 text-center">
                        <Checkbox 
                          checked={isAvailable}
                          onCheckedChange={() => toggleDayAvailability(day)}
                        />
                      </td>
                      {periods.map(p => {
                        const isBlocked = dayAvail?.blocked_periods?.includes(p) || false;
                        return (
                          <td key={p} className="p-1 text-center">
                            <button
                              type="button"
                              disabled={!isAvailable}
                              onClick={() => togglePeriodBlocked(day, p)}
                              className={`
                                w-8 h-8 rounded border text-xs font-medium transition-colors
                                ${!isAvailable 
                                  ? 'bg-muted text-muted-foreground cursor-not-allowed'
                                  : isBlocked
                                    ? 'bg-red-500 text-white border-red-600 hover:bg-red-600'
                                    : 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 border-green-300 dark:border-green-700 hover:bg-green-200 dark:hover:bg-green-900/50'
                                }
                              `}
                            >
                              {isBlocked ? <X className="w-4 h-4 mx-auto" /> : '✓'}
                            </button>
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <span className="w-4 h-4 bg-green-100 dark:bg-green-900/30 rounded border border-green-300"></span>
              Available
            </span>
            <span className="flex items-center gap-1">
              <span className="w-4 h-4 bg-red-500 rounded"></span>
              Blocked
            </span>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setTeacherAvailabilityModal(false)}>
              Cancel
            </Button>
            <Button onClick={saveTeacherAvailability}>
              Save Availability
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Resource Configuration Modal */}
      <Dialog open={resourceConfigModal} onOpenChange={setResourceConfigModal}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle>Configure: {selectedResource?.name || selectedResource?.resource_id}</DialogTitle>
            <DialogDescription>
              Set the maximum number of sections that can use this resource simultaneously.
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Resource Type</Label>
              <p className="text-sm text-muted-foreground">{selectedResource?.resource_type}</p>
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="resource-capacity">Max Simultaneous Capacity</Label>
              <Select
                value={String(editingResourceCapacity)}
                onValueChange={(v) => setEditingResourceCapacity(parseInt(v))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {[1, 2, 3, 4, 5, 6].map(n => (
                    <SelectItem key={n} value={String(n)}>
                      {n} section{n > 1 ? 's' : ''}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                How many classes can use this resource at the same time?
              </p>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setResourceConfigModal(false)}>
              Cancel
            </Button>
            <Button onClick={saveResourceConfig}>
              Save Configuration
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Subject Time Restriction Modal */}
      <Dialog open={subjectModal} onOpenChange={setSubjectModal}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>Time Restrictions: {selectedSubject?.name}</DialogTitle>
            <DialogDescription>
              Select the days and periods when this subject can be scheduled.
              Unselected items will be blocked.
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-6 py-4">
            {/* Allowed Days */}
            <div className="space-y-3">
              <Label className="text-sm font-medium">Allowed Days</Label>
              <div className="flex flex-wrap gap-2">
                {weekdays.map(day => (
                  <button
                    key={day}
                    type="button"
                    onClick={() => toggleSubjectDay(day)}
                    className={`
                      px-4 py-2 rounded-lg border text-sm font-medium transition-colors
                      ${editingSubjectAllowedDays.includes(day)
                        ? 'bg-primary text-primary-foreground border-primary'
                        : 'bg-muted text-muted-foreground border-border hover:bg-muted/80'
                      }
                    `}
                  >
                    {day}
                  </button>
                ))}
              </div>
              <p className="text-xs text-muted-foreground">
                Click to toggle. Green = allowed, gray = blocked.
              </p>
            </div>
            
            {/* Allowed Periods */}
            <div className="space-y-3">
              <Label className="text-sm font-medium">Allowed Periods</Label>
              <div className="flex flex-wrap gap-2">
                {periods.map(period => (
                  <button
                    key={period}
                    type="button"
                    onClick={() => toggleSubjectPeriod(period)}
                    className={`
                      w-12 h-12 rounded-lg border text-sm font-medium transition-colors
                      ${editingSubjectAllowedPeriods.includes(period)
                        ? 'bg-primary text-primary-foreground border-primary'
                        : 'bg-muted text-muted-foreground border-border hover:bg-muted/80'
                      }
                    `}
                  >
                    P{period}
                  </button>
                ))}
              </div>
              <p className="text-xs text-muted-foreground">
                Example: For "9am-12pm only", select periods 1-4 (based on your school timing).
              </p>
            </div>

            {/* Current settings summary */}
            <div className="p-3 bg-muted/50 rounded-lg text-sm">
              <p className="font-medium mb-1">Current Restrictions:</p>
              <p>
                Days: {editingSubjectAllowedDays.length === weekdays.length 
                  ? 'All days allowed' 
                  : editingSubjectAllowedDays.length === 0 
                    ? 'No days selected!' 
                    : editingSubjectAllowedDays.join(', ')}
              </p>
              <p>
                Periods: {editingSubjectAllowedPeriods.length === periods.length 
                  ? 'All periods allowed'
                  : editingSubjectAllowedPeriods.length === 0
                    ? 'No periods selected!'
                    : `P${editingSubjectAllowedPeriods.join(', P')}`}
              </p>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setSubjectModal(false)}>
              Cancel
            </Button>
            <Button 
              onClick={saveSubjectRestriction}
              disabled={editingSubjectAllowedDays.length === 0 || editingSubjectAllowedPeriods.length === 0}
            >
              Save Restriction
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Actions */}
      <div className="flex justify-between">
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate('/upload')}>
            <ChevronLeft className="h-4 w-4 mr-2" />
            Back to Upload
          </Button>
          <Button variant="outline" onClick={handleReset}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Reset Defaults
          </Button>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleSubmit(onSubmit)}>
            <Save className="h-4 w-4 mr-2" />
            Save
          </Button>
          <Button onClick={handleContinue}>
            Continue to Generate
            <ChevronRight className="h-4 w-4 ml-2" />
          </Button>
        </div>
      </div>
    </div>
  );
}
