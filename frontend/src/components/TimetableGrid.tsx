import { useMemo } from 'react';
import { cn, formatTime } from '@/lib/utils';

// Types
interface Period {
  day: string;
  period: number;
  subject_id: string;
  subject_name: string;
  teacher_id?: string;
  teacher_name?: string;
  room_id?: string;
  room_name?: string;
  class_id?: string;
  class_name?: string;
}

interface TimetableGridProps {
  periods: Period[];
  days: string[];
  periodsPerDay: number;
  periodTimes?: Array<{ start: string; end: string }>;
  viewMode: 'class' | 'teacher' | 'resource';
  subjectColorMap: Record<string, string>;
  onPeriodClick?: (period: Period) => void;
  className?: string;
}

// Default color palette for subjects
const DEFAULT_SUBJECT_COLORS = [
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

/**
 * Generate a color map for subjects
 */
export function generateSubjectColorMap(subjects: string[]): Record<string, string> {
  const map: Record<string, string> = {};
  subjects.forEach((subject, i) => {
    map[subject] = DEFAULT_SUBJECT_COLORS[i % DEFAULT_SUBJECT_COLORS.length];
  });
  return map;
}

/**
 * Reusable timetable grid component for displaying class/teacher/resource schedules
 */
export function TimetableGrid({
  periods,
  days,
  periodsPerDay,
  periodTimes,
  viewMode,
  subjectColorMap,
  onPeriodClick,
  className,
}: TimetableGridProps) {
  // Build a lookup for quick period access
  const periodLookup = useMemo(() => {
    const lookup: Record<string, Period> = {};
    periods.forEach((p) => {
      const key = `${p.day}-${p.period}`;
      lookup[key] = p;
    });
    return lookup;
  }, [periods]);

  const handlePeriodClick = (period: Period | undefined) => {
    if (period && onPeriodClick) {
      onPeriodClick(period);
    }
  };

  // Get secondary info based on view mode
  const getSecondaryInfo = (period: Period): string | null => {
    switch (viewMode) {
      case 'class':
        return period.teacher_name || null;
      case 'teacher':
        return period.class_name || null;
      case 'resource':
        return period.teacher_name || period.class_name || null;
      default:
        return null;
    }
  };

  return (
    <div className={cn('overflow-x-auto', className)}>
      <table className="w-full min-w-[800px] border-collapse">
        <thead>
          <tr className="bg-muted/50">
            <th className="w-24 p-3 border text-left text-sm font-medium">Time</th>
            {days.map((day) => (
              <th key={day} className="p-3 border text-center text-sm font-medium">
                {day}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: periodsPerDay }, (_, periodIdx) => {
            const time = periodTimes?.[periodIdx];
            return (
              <tr key={periodIdx}>
                <td className="p-2 border bg-muted/30 text-sm">
                  <div className="font-medium">Period {periodIdx + 1}</div>
                  {time && (
                    <div className="text-xs text-muted-foreground">
                      {formatTime(time.start)} - {formatTime(time.end)}
                    </div>
                  )}
                </td>
                {days.map((day) => {
                  const period = periodLookup[`${day}-${periodIdx + 1}`];
                  return (
                    <td
                      key={day}
                      className={cn(
                        'p-1 border transition-colors',
                        period && 'cursor-pointer hover:bg-muted/50',
                        !period && 'bg-muted/10'
                      )}
                      onClick={() => handlePeriodClick(period)}
                    >
                      {period && (
                        <div
                          className={cn(
                            'p-2 rounded border text-xs',
                            subjectColorMap[period.subject_id] || 'bg-gray-100 border-gray-300'
                          )}
                        >
                          <div className="font-medium truncate" title={period.subject_name}>
                            {period.subject_name}
                          </div>
                          {getSecondaryInfo(period) && (
                            <div className="text-xs opacity-80 truncate" title={getSecondaryInfo(period) || ''}>
                              {getSecondaryInfo(period)}
                            </div>
                          )}
                          {period.room_name && (
                            <div className="text-xs opacity-60 truncate mt-0.5" title={period.room_name}>
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
          })}
        </tbody>
      </table>
    </div>
  );
}

/**
 * Subject color legend component
 */
interface SubjectLegendProps {
  subjectColorMap: Record<string, string>;
  subjectNames?: Record<string, string>;
  className?: string;
}

export function SubjectLegend({
  subjectColorMap,
  subjectNames,
  className,
}: SubjectLegendProps) {
  return (
    <div className={cn('flex flex-wrap gap-2', className)}>
      {Object.entries(subjectColorMap).map(([subjectId, colorClass]) => (
        <div
          key={subjectId}
          className={cn('px-3 py-1 rounded border text-xs font-medium', colorClass)}
          title={subjectNames?.[subjectId] || subjectId}
        >
          {subjectNames?.[subjectId] || subjectId}
        </div>
      ))}
    </div>
  );
}

/**
 * Empty cell placeholder for breaks/free periods
 */
export function EmptyPeriodCell({ label = 'Free' }: { label?: string }) {
  return (
    <div className="p-2 text-center text-xs text-muted-foreground italic">
      {label}
    </div>
  );
}
