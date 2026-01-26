import { Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from '@/components/ui/toaster';
import { AppLayout } from '@/layouts/AppLayout';
import { LandingPage } from '@/pages/LandingPage';
import { UploadPage } from '@/pages/UploadPage';
import { ConstraintsPage } from '@/pages/ConstraintsPage';
import { GeneratePage } from '@/pages/GeneratePage';
import { ResultsPage } from '@/pages/ResultsPage';
import { RecentJobsPage } from '@/pages/RecentJobsPage';

function App() {
  return (
    <>
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<LandingPage />} />
          <Route path="upload" element={<UploadPage />} />
          <Route path="constraints" element={<ConstraintsPage />} />
          <Route path="generate" element={<GeneratePage />} />
          <Route path="results/:jobId" element={<ResultsPage />} />
          <Route path="jobs" element={<RecentJobsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
      <Toaster />
    </>
  );
}

export default App;
