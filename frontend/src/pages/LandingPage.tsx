import { Link } from 'react-router-dom';
import {
  Calendar,
  Upload,
  Settings2,
  ArrowRight,
  Clock,
  CheckCircle,
  Zap,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

const features = [
  {
    icon: Upload,
    title: 'Easy Data Import',
    description: 'Upload your school data via Excel or CSV files with automatic validation.',
  },
  {
    icon: Settings2,
    title: 'Flexible Constraints',
    description: 'Configure teacher availability, room resources, and scheduling preferences.',
  },
  {
    icon: Zap,
    title: 'Intelligent Solver',
    description: 'Powered by OR-Tools for optimal timetable generation with constraint satisfaction.',
  },
  {
    icon: Clock,
    title: 'Fast Generation',
    description: 'Generate complete timetables in seconds, even for large schools.',
  },
];

const steps = [
  {
    number: 1,
    title: 'Upload Your Data',
    description: 'Import teachers, subjects, classes, and resources.',
    href: '/upload',
  },
  {
    number: 2,
    title: 'Configure Constraints',
    description: 'Set scheduling rules and preferences.',
    href: '/constraints',
  },
  {
    number: 3,
    title: 'Generate Timetable',
    description: 'Let the solver create an optimal schedule.',
    href: '/generate',
  },
];

export function LandingPage() {
  return (
    <div className="space-y-8">
      {/* Hero Section */}
      <section className="text-center py-12">
        <div className="flex justify-center mb-6">
          <div className="rounded-full bg-primary/10 p-4">
            <Calendar className="h-12 w-12 text-primary" />
          </div>
        </div>
        <h1 className="text-4xl font-bold tracking-tight mb-4">
          School Timetable Generator
        </h1>
        <p className="text-lg text-muted-foreground max-w-2xl mx-auto mb-8">
          Create optimal school timetables automatically. Our intelligent solver handles
          complex constraints to produce conflict-free schedules in seconds.
        </p>
        <div className="flex justify-center gap-4">
          <Button asChild size="lg">
            <Link to="/upload">
              Get Started
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
          <Button asChild variant="outline" size="lg">
            <Link to="/jobs">View Recent Jobs</Link>
          </Button>
        </div>
      </section>

      {/* Features Grid */}
      <section>
        <h2 className="text-2xl font-semibold text-center mb-6">Key Features</h2>
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          {features.map((feature) => (
            <Card key={feature.title}>
              <CardHeader className="pb-2">
                <feature.icon className="h-8 w-8 text-primary mb-2" />
                <CardTitle className="text-lg">{feature.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <CardDescription>{feature.description}</CardDescription>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* How It Works */}
      <section className="py-8">
        <h2 className="text-2xl font-semibold text-center mb-8">How It Works</h2>
        <div className="grid gap-6 md:grid-cols-3">
          {steps.map((step, index) => (
            <Card key={step.number} className="relative">
              <CardHeader>
                <div className="flex items-center gap-4">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary text-primary-foreground font-bold">
                    {step.number}
                  </div>
                  <CardTitle className="text-lg">{step.title}</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <CardDescription className="mb-4">{step.description}</CardDescription>
                <Button asChild variant="outline" size="sm">
                  <Link to={step.href}>
                    {step.number === 3 ? 'Generate' : 'Start'}
                    <ArrowRight className="ml-2 h-3 w-3" />
                  </Link>
                </Button>
              </CardContent>
              {index < steps.length - 1 && (
                <div className="hidden md:block absolute top-1/2 -right-3 transform -translate-y-1/2">
                  <ArrowRight className="h-6 w-6 text-muted-foreground" />
                </div>
              )}
            </Card>
          ))}
        </div>
      </section>

      {/* Quick Stats / Benefits */}
      <section className="py-8 bg-muted/30 -mx-6 px-6 rounded-lg">
        <div className="grid gap-6 md:grid-cols-3 text-center">
          <div>
            <CheckCircle className="h-8 w-8 text-success mx-auto mb-2" />
            <h3 className="text-2xl font-bold">100%</h3>
            <p className="text-muted-foreground">Conflict-free schedules</p>
          </div>
          <div>
            <Clock className="h-8 w-8 text-primary mx-auto mb-2" />
            <h3 className="text-2xl font-bold">&lt; 30s</h3>
            <p className="text-muted-foreground">Average generation time</p>
          </div>
          <div>
            <Settings2 className="h-8 w-8 text-primary mx-auto mb-2" />
            <h3 className="text-2xl font-bold">20+</h3>
            <p className="text-muted-foreground">Configurable constraints</p>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="text-center py-8">
        <h2 className="text-2xl font-semibold mb-4">Ready to Create Your Timetable?</h2>
        <p className="text-muted-foreground mb-6">
          Upload your data and generate an optimal schedule in minutes.
        </p>
        <Button asChild size="lg">
          <Link to="/upload">
            Start Now
            <ArrowRight className="ml-2 h-4 w-4" />
          </Link>
        </Button>
      </section>
    </div>
  );
}
