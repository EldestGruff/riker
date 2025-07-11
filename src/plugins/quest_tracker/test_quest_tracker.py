import pytest
from unittest.mock import Mock, patch, MagicMock
from .plugin_interface import QuestTracker
from .quest_parser import QuestParser, ParsedMission, MissionObjective, AcceptanceCriteria

class TestGitHubManager:
    
    def test_github_manager_init_with_params(self):
        """Test GitHub manager initialization with parameters"""
        with patch('src.plugins.quest_tracker.plugin_interface.Github') as mock_github:
            mock_repo = Mock()
            mock_repo.name = "test-repo"
            mock_github.return_value.get_repo.return_value = mock_repo
            
            manager = QuestTracker(token="test-token", repo_name="test/repo")
            
            mock_github.assert_called_once_with("test-token")
            assert manager.repo_name == "test/repo"
            assert manager.token == "test-token"
    
    def test_github_manager_init_with_env_vars(self):
        """Test GitHub manager initialization with environment variables"""
        with patch('src.plugins.quest_tracker.plugin_interface.Github') as mock_github, \
             patch('os.getenv') as mock_getenv:
            
            mock_getenv.side_effect = lambda key: {
                'GITHUB_TOKEN': 'env-token',
                'GITHUB_REPO': 'env/repo'
            }.get(key)
            
            mock_repo = Mock()
            mock_repo.name = "env-repo"
            mock_github.return_value.get_repo.return_value = mock_repo
            
            manager = QuestTracker()
            
            mock_github.assert_called_once_with("env-token")
            assert manager.repo_name == "env/repo"
            assert manager.token == "env-token"
    
    def test_github_manager_init_missing_token(self):
        """Test GitHub manager initialization fails without token"""
        with patch('os.getenv', return_value=None):
            with pytest.raises(ValueError, match="GitHub token is required"):
                QuestTracker()
    
    def test_get_away_quests(self):
        """Test fetching quests"""
        with patch('src.plugins.quest_tracker.plugin_interface.Github') as mock_github:
            # Setup mocks
            mock_repo = Mock()
            mock_github.return_value.get_repo.return_value = mock_repo
            
            mock_issue = Mock()
            mock_issue.number = 1
            mock_issue.title = "Test Quest"
            mock_issue.state = "open"
            mock_issue.html_url = "https://github.com/test/repo/issues/1"
            mock_issue.created_at = Mock()
            mock_issue.created_at.isoformat.return_value = "2023-01-01T00:00:00"
            mock_issue.updated_at = Mock()
            mock_issue.updated_at.isoformat.return_value = "2023-01-02T00:00:00"
            mock_issue.body = """
# Quest Brief: Test Quest

**Quest ID:** QUEST-001
**Classification:** 🔴 Priority One

## 🎯 Quest Objectives

### Primary Objective
Test the system

## 📋 Acceptance Criteria
- [ ] System works
- [ ] Tests pass
"""
            
            mock_repo.get_issues.return_value = [mock_issue]
            
            manager = QuestTracker(token="test-token", repo_name="test/repo")
            missions = manager.get_away_quests("open")
            
            assert len(missions) == 1
            assert missions[0]['number'] == 1
            assert missions[0]['title'] == "Test Quest"
            assert missions[0]['quest_id'] == "QUEST-001"
            assert missions[0]['classification'] == "🔴 Priority One"
            mock_repo.get_issues.assert_called_once_with(state="open", labels=['quest'])
    
    def test_create_feature_branch(self):
        """Test branch creation"""
        with patch('src.plugins.quest_tracker.plugin_interface.Github') as mock_github:
            mock_repo = Mock()
            mock_github.return_value.get_repo.return_value = mock_repo
            
            mock_main_ref = Mock()
            mock_main_ref.object.sha = "abc123"
            mock_repo.get_git_ref.return_value = mock_main_ref
            
            manager = QuestTracker(token="test-token", repo_name="test/repo")
            branch_name = manager.create_feature_branch(1, "Test Quest Feature")
            
            expected_branch = "quest-1-test-quest-feature"
            assert branch_name == expected_branch
            
            mock_repo.get_git_ref.assert_called_once_with("heads/main")
            mock_repo.create_git_ref.assert_called_once_with(
                ref=f"refs/heads/{expected_branch}",
                sha="abc123"
            )
    
    def test_update_quest_progress(self):
        """Test updating quest progress"""
        with patch('src.plugins.quest_tracker.plugin_interface.Github') as mock_github:
            mock_repo = Mock()
            mock_github.return_value.get_repo.return_value = mock_repo
            
            mock_issue = Mock()
            mock_issue.labels = []
            mock_repo.get_issue.return_value = mock_issue
            
            manager = QuestTracker(token="test-token", repo_name="test/repo")
            success = manager.update_quest_progress(1, "in-progress", "Starting work")
            
            assert success is True
            mock_repo.get_issue.assert_called_once_with(1)
            mock_issue.create_comment.assert_called_once()
            mock_issue.add_to_labels.assert_called_once_with("in-progress")


class TestMissionParser:
    
    def test_parse_quest_basic(self):
        """Test basic quest parsing"""
        parser = QuestParser()
        
        sample_body = """
# Quest Brief: Implement Test Feature

**Quest ID:** QUEST-001
**Classification:** 🔴 Priority One
**Type:** Feature Implementation

## 🎯 Quest Objectives

### Primary Objective
Implement the test feature

### Secondary Objectives
- [ ] Write tests
- [ ] Update documentation

## 📋 Acceptance Criteria
- [ ] Feature works as expected
- [ ] All tests pass
- [ ] Documentation updated

## 🔧 Technical Specifications
- **Framework:** React
- **Testing:** Jest

## 👨‍✈️ Archmage's Notes
This is a high priority feature.

## Referenced Documents
- [API Spec](grimoire/api-spec.md)
"""
        
        result = parser.parse_quest(1, "Test Quest", sample_body)
        
        assert result.number == 1
        assert result.title == "Test Quest"
        assert result.quest_id == "QUEST-001"
        assert result.classification == "🔴 Priority One"
        assert result.quest_type == "Feature Implementation"
        
        # Check objectives
        assert len(result.objectives) == 3
        assert result.objectives[0].description == "Implement the test feature"
        assert result.objectives[0].is_primary is True
        assert result.objectives[1].description == "Write tests"
        assert result.objectives[1].is_primary is False
        
        # Check acceptance criteria
        assert len(result.acceptance_criteria) == 3
        assert result.acceptance_criteria[0].description == "Feature works as expected"
        assert result.acceptance_criteria[0].is_complete is False
        
        # Check technical specs
        assert result.technical_specs['Framework'] == 'React'
        assert result.technical_specs['Testing'] == 'Jest'
        
        # Check archmage's notes
        assert result.captains_notes == "This is a high priority feature."
        
        # Check referenced docs
        assert "grimoire/api-spec.md" in result.referenced_docs
    
    def test_parse_quest_minimal(self):
        """Test parsing quest with minimal content"""
        parser = QuestParser()
        
        sample_body = """
Basic quest description without proper formatting.
"""
        
        result = parser.parse_quest(2, "Minimal Quest", sample_body)
        
        assert result.number == 2
        assert result.title == "Minimal Quest"
        assert result.quest_id == "UNKNOWN"
        assert result.classification == "Standard"
        assert result.quest_type == "General"
        assert len(result.objectives) == 0
        assert len(result.acceptance_criteria) == 0
    
    def test_extract_objectives_primary_secondary(self):
        """Test extracting objectives with primary/secondary structure"""
        parser = QuestParser()
        
        body = """
## Quest Objectives

### Primary Objective
Complete the main task

### Secondary Objectives
- [ ] Task 1
- [ ] Task 2
- Task 3 without checkbox
"""
        
        objectives = parser.extract_objectives(body)
        
        assert len(objectives) == 4
        assert objectives[0].description == "Complete the main task"
        assert objectives[0].is_primary is True
        assert objectives[1].description == "Task 1"
        assert objectives[1].is_primary is False
        assert objectives[2].description == "Task 2"
        assert objectives[2].is_primary is False
        assert objectives[3].description == "Task 3 without checkbox"
        assert objectives[3].is_primary is False
    
    def test_extract_acceptance_criteria_with_checkboxes(self):
        """Test extracting acceptance criteria with checkboxes"""
        parser = QuestParser()
        
        body = """
## Acceptance Criteria
- [x] Completed task
- [ ] Pending task
- [X] Another completed task
"""
        
        criteria = parser.extract_acceptance_criteria(body)
        
        assert len(criteria) == 3
        assert criteria[0].description == "Completed task"
        assert criteria[0].is_complete is True
        assert criteria[1].description == "Pending task"
        assert criteria[1].is_complete is False
        assert criteria[2].description == "Another completed task"
        assert criteria[2].is_complete is True
    
    def test_extract_referenced_docs(self):
        """Test extracting referenced documentation"""
        parser = QuestParser()
        
        body = """
See [API Spec](grimoire/api-spec.md) for details.
Also check the database spec: grimoire/database-spec.md
And the [UI Guidelines](docs/ui-guidelines.md).
"""
        
        docs = parser.extract_referenced_docs(body)
        
        assert "grimoire/api-spec.md" in docs
        assert "grimoire/database-spec.md" in docs
        assert "docs/ui-guidelines.md" in docs
    
    def test_quest_type_inference(self):
        """Test quest type inference from content"""
        parser = QuestParser()
        
        # Test bug fix detection
        body1 = "This is a bug fix for the login issue"
        result1 = parser._extract_quest_type(body1)
        assert result1 == "Bug Fix"
        
        # Test feature implementation detection
        body2 = "Implement new feature for user dashboard"
        result2 = parser._extract_quest_type(body2)
        assert result2 == "Feature Implementation"
        
        # Test refactoring detection
        body3 = "Refactor the authentication module"
        result3 = parser._extract_quest_type(body3)
        assert result3 == "Refactoring"
        
        # Test documentation detection
        body4 = "Update documentation for the API"
        result4 = parser._extract_quest_type(body4)
        assert result4 == "Documentation"
    
    def test_classification_extraction(self):
        """Test classification/priority extraction"""
        parser = QuestParser()
        
        body1 = "**Classification:** 🔴 Priority One"
        result1 = parser._extract_classification(body1)
        assert result1 == "🔴 Priority One"
        
        body2 = "Priority: High"
        result2 = parser._extract_classification(body2)
        assert result2 == "High"
        
        body3 = "🟡 Priority Three"
        result3 = parser._extract_classification(body3)
        assert result3 == "🟡 Priority Three"


if __name__ == '__main__':
    pytest.main([__file__])