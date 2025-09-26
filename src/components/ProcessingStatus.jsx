import React from 'react';
import { Loader2, Eye, Brain, Tags, Target, Clock, FileSearch } from 'lucide-react';

const ProcessingStatus = ({ stage, progress }) => {
  const stages = [
    { id: 'extracting', label: 'Extracting Text', icon: Eye, description: 'Reading document content with OCR...' },
    { id: 'classifying', label: 'Department Classification', icon: Tags, description: 'Determining KMRL department...' },
    { id: 'summarizing', label: 'Detailed Analysis', icon: Brain, description: 'Generating comprehensive summary...' },
    { id: 'extracting-purpose', label: 'Purpose & Actions', icon: Target, description: 'Identifying objectives & actions...' },
    { id: 'extracting-details', label: 'Additional Details', icon: FileSearch, description: 'Extracting compliance & risk info...' },
    { id: 'finalizing', label: 'Finalizing', icon: Clock, description: 'Preparing results...' }
  ];

  const currentStageIndex = stages.findIndex(s => s.id === stage);

  return (
    <div className="processing-status fade-in-up">
      <div className="processing-header">
        <Loader2 className="spinner" size={32} />
        <h3>Processing Document...</h3>
      </div>
      
      <div className="progress-bar">
        <div 
          className="progress-fill" 
          style={{ width: `${progress}%` }}
        ></div>
      </div>
      
      <div className="progress-text">
        <span>{progress}% Complete</span>
      </div>
      
      <div className="stages">
        {stages.map((stageItem, index) => {
          const Icon = stageItem.icon;
          const isActive = index === currentStageIndex;
          const isCompleted = index < currentStageIndex;
          
          return (
            <div 
              key={stageItem.id} 
              className={`stage ${isActive ? 'active' : ''} ${isCompleted ? 'completed' : ''}`}
            >
              <div className="stage-icon">
                <Icon size={20} />
              </div>
              <div className="stage-content">
                <h4>{stageItem.label}</h4>
                {isActive && <p>{stageItem.description}</p>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ProcessingStatus;