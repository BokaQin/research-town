from unittest.mock import MagicMock, patch

from research_town.agents import AgentManager
from research_town.dbs import LogDB, PaperDB, ProfileDB, ProgressDB
from research_town.envs import ProposalWritingwithRAGEnv, ReviewWritingEnv
from tests.constants.config_constants import example_config
from tests.constants.data_constants import (
    profile_A,
    research_proposal_A,
    research_proposal_B,
)
from tests.mocks.mocking_func import mock_prompting


@patch('research_town.utils.agent_prompter.model_prompting')
def test_review_writing_env(
    mock_model_prompting: MagicMock,
    example_profile_db: ProfileDB,
    example_log_db: LogDB,
    example_progress_db: ProgressDB,
    example_paper_db: PaperDB,
    example_agent_manager: AgentManager,
) -> None:
    mock_model_prompting.side_effect = mock_prompting

    example_profile_db.reset_role_availability()
    env = ReviewWritingEnv(
        name='review_writing',
        log_db=example_log_db,
        progress_db=example_progress_db,
        paper_db=example_paper_db,
        config=example_config,
        agent_manager=example_agent_manager,
    )
    leader = example_agent_manager.create_agent(profile=profile_A, role='leader')
    env.on_enter(
        proposals=[research_proposal_A, research_proposal_B],
        leader=leader,
    )
    run_result = env.run()
    if run_result is not None:
        for progress, agent in run_result:
            pass
    exit_status, exit_dict = env.on_exit()

    assert exit_status == 'proposal_accept'
    assert exit_dict['metareviews'] is not None


@patch('research_town.utils.agent_prompter.model_prompting')
def test_proposal_writing_env(
    mock_model_prompting: MagicMock,
    example_profile_db: ProfileDB,
    example_log_db: LogDB,
    example_progress_db: ProgressDB,
    example_paper_db: PaperDB,
    example_agent_manager: AgentManager,
) -> None:
    mock_model_prompting.side_effect = mock_prompting

    example_profile_db.reset_role_availability()
    env = ProposalWritingwithRAGEnv(
        name='proposal_writing',
        log_db=example_log_db,
        progress_db=example_progress_db,
        paper_db=example_paper_db,
        config=example_config,
        agent_manager=example_agent_manager,
    )
    leader = example_agent_manager.create_agent(profile=profile_A, role='leader')
    env.on_enter(
        leader=leader,
        contexts=[
            "Much of the world's most valued data is stored in relational databases and data warehouses, where the data is organized into many tables connected by primary-foreign key relations. However, building machine learning models using this data is both challenging and time consuming. The core problem is that no machine learning method is capable of learning on multiple tables interconnected by primary-foreign key relations. Current methods can only learn from a single table, so the data must first be manually joined and aggregated into a single training table, the process known as feature engineering. Feature engineering is slow, error prone and leads to suboptimal models. Here we introduce an end-to-end deep representation learning approach to directly learn on data laid out across multiple tables. We name our approach Relational Deep Learning (RDL). The core idea is to view relational databases as a temporal, heterogeneous graph, with a node for each row in each table, and edges specified by primary-foreign key links. Message Passing Graph Neural Networks can then automatically learn across the graph to extract representations that leverage all input data, without any manual feature engineering. Relational Deep Learning leads to more accurate models that can be built much faster. To facilitate research in this area, we develop RelBench, a set of benchmark datasets and an implementation of Relational Deep Learning. The data covers a wide spectrum, from discussions on Stack Exchange to book reviews on the Amazon Product Catalog. Overall, we define a new research area that generalizes graph machine learning and broadens its applicability to a wide set of AI use cases."
        ],
    )
    run_result = env.run()
    if run_result is not None:
        for progress, agent in run_result:
            pass
    exit_status, exit_dict = env.on_exit()
    assert exit_status == 'start_review'

    proposals = exit_dict['proposals']
    for proposal in proposals:
        assert proposal.content is not None
        assert proposal.content == 'Paper abstract1'
