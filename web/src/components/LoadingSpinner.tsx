import React from 'react';

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  message?: string;
  className?: string;
}

const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = 'md',
  message = 'Loading...',
  className = ''
}) => {
  const sizeClasses = {
    sm: 'w-8 h-8',
    md: 'w-12 h-12',
    lg: 'w-16 h-16'
  };

  return (
    <div className={`flex flex-col items-center justify-center space-y-4 ${className}`}>
      <div className="relative">
        <div className={`${sizeClasses[size]} rounded-full border-2 border-blue-600 animate-pulse`}></div>
        <div className={`absolute top-0 left-0 ${sizeClasses[size]} rounded-full border-t-2 border-blue-600 animate-spin`}></div>
      </div>
      {message && (
        <p className="text-gray-500 animate-pulse">{message}</p>
      )}
    </div>
  );
};

export default LoadingSpinner; 