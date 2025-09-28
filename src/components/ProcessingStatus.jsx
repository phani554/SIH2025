import React from 'react';
import { Loader2, Eye, Brain, Tags, Target, Clock, FileSearch } from 'lucide-react';

const ProcessingStatus = ({ stage, progress }) => {
  const stages = [
    { id: 'extracting', label: 'Reading Document', icon: Eye},
    { id: 'classifying', label: 'Classifying Department', icon: Tags},
    { id: 'summarizing', label: 'Generating Summary', icon: Brain},
    { id: 'extracting-purpose', label: 'Identifying Actions', icon: Target},
    { id: 'extracting-details', label: 'Analysing Risk Info', icon: FileSearch},
    { id: 'finalizing', label: 'Finalizing', icon: Clock}
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
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ProcessingStatus;