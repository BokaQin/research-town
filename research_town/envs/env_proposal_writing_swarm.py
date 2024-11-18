from beartype import beartype
from beartype.typing import Any, Dict, Generator, List, Tuple
from swarm import Swarm

from ..agents import Agent, AgentManager
from ..configs import Config
from ..data import Insight, Progress, Proposal
from ..dbs import LogDB, PaperDB, ProgressDB
from .env_base import BaseEnv


class ProposalWritingSWARM(BaseEnv):
    def __init__(
        self,
        name: str,
        log_db: LogDB,
        progress_db: ProgressDB,
        paper_db: PaperDB,
        config: Config,
        agent_manager: AgentManager,
    ) -> None:
        super().__init__(name=name, config=config)
        self.log_db = log_db
        self.progress_db = progress_db
        self.paper_db = paper_db
        self.agent_manager = agent_manager
        self.proposals: List[Proposal] = []
        self.client = Swarm()

    @beartype
    def on_enter(self, **context: Any) -> None:
        # Assign leader and members from context or sample them
        self.leader = context.get('leader', self.agent_manager.sample_leader())
        self.members = context.get('members', self.agent_manager.sample_members())

        if 'contexts' not in context:
            raise ValueError("'contexts' is required in the context.")
        self.contexts = context['contexts']
        self.contexts = [
            context if context else '' for context in self.contexts
        ]  # remove None

    @beartype
    def on_exit(self) -> Tuple[str, Dict[str, Any]]:
        # Update environment run number and handle limits
        self.env_run_num += 1
        if self.env_run_num > self.config.param.max_env_run_num:
            return 'error', {}  # Return error if max run limit exceeded
        return 'start_review', {'proposals': self.proposals, 'leader': self.leader}

    @beartype
    def run(self) -> Generator[Tuple[Progress, Agent], None, None]:
        accumulated_insights: List[Insight] = []
        k: int = self.config.param.discussion_rounds

        for round_num in range(k):
            round_insights = []
            researchers = self.members + [self.leader]

            for researcher in researchers:
                search_query = (
                    ' '.join(insight.content for insight in accumulated_insights)
                    if accumulated_insights
                    else ';'.join(self.contexts)
                )
                related_papers = self.paper_db.search_papers(
                    query=search_query,
                    num=self.config.param.related_paper_num,
                )

                messages = [
                    {
                        'role': 'user',
                        'content': 'Please summarize your provided related papers in 200 words. Ground on related papers and use [1], [2], ... to refer to them. Please ensure that no identical citations point to different URLs, and no different citations point to the same URL.',
                    }
                ]

                response = self.client.run(
                    agent=researcher,
                    messages=messages,
                    context_variables={'papers': related_papers},
                )

                # summary = response.messages[-1]['content']
                messages.extend(response.messages)

                messages.append(
                    {
                        'role': 'user',
                        'content': 'Please summarize 10 keywords from your summary.\nGround on related papers and use [1], [2], ... to refer to them. Please ensure that no identical citations point to different URLs, and no different citations point to the same URL.',
                    }
                )

                response = self.client.run(
                    agent=researcher,
                    messages=messages,
                    context_variables={'papers': related_papers},
                )
                messages.extend(response.messages)

                # keywords = response.messages[-1]['content']

                messages.append(
                    {
                        'role': 'user',
                        'content': (
                            f'Round {round_num + 1} discussion based on literature review summary and keywords.\n'
                            f'Please provide your new research insights based on your expertise.\n'
                            f'Ground on related papers and use [1], [2], ... to refer to them. Please ensure that no identical citations point to different URLs, and no different citations point to the same URL.'
                        ),
                    }
                )

                response = self.client.run(
                    agent=researcher,
                    messages=messages,
                    context_variables={'papers': related_papers},
                )
                messages.extend(response.messages)

                insight = response.messages[-1]['content']

                print(insight)

                # Log each researcher's insight
                insight_obj = Insight(content=insight)

                yield insight_obj, researcher
                round_insights.append(insight_obj)

            accumulated_insights.extend(round_insights)

        # Final step: Leader generates the proposal based on all accumulated insights
        combined_summary = ' '.join(insight.content for insight in accumulated_insights)
        final_related_papers = self.paper_db.search_papers(
            query=combined_summary,
            num=self.config.param.related_paper_num,
        )

        messages = [
            {
                'role': 'user',
                'content': (
                    f'Generate a research proposal based on accumulated insights and your provided related papers.\n'
                    f'Accumulated: {combined_summary}\n'
                    'First question to answer:'
                    '[Question 1] - What is the problem?\n\n'
                    'Formulate the specific research question you aim to address. Only output one question and do not include any more information.\n\n'
                    'Response in 100 words. Use declarative sentences instead of interrogative ones. Ground on related papers and use [1], [2], ... to refer to them. Please ensure that no identical citations point to different URLs, and no different citations point to the same URL.'
                ),
            }
        ]

        response = self.client.run(
            agent=self.leader,
            messages=messages,
            context_variables={'papers': final_related_papers},
        )

        q1 = response.messages[-1]['content']
        messages.extend(response.messages)

        messages.append(
            {
                'role': 'user',
                'content': (
                    '[Question 2] - Why is it interesting and important?\n\n'
                    'Explain the broader implications of solving this problem for the research community.\n'
                    'Discuss how such paper will affect the future research.\n'
                    'Discuss how addressing this question could advance knowledge or lead to practical applications.\n\n'
                    'Response in 100 words. Use declarative sentences instead of interrogative ones. Ground on related papers and use [1], [2], ... to refer to them. Please ensure that no identical citations point to different URLs, and no different citations point to the same URL.'
                ),
            }
        )

        response = self.client.run(
            agent=self.leader,
            messages=messages,
            context_variables={'papers': final_related_papers},
        )

        q2 = response.messages[-1]['content']
        messages.extend(response.messages)

        messages.append(
            {
                'role': 'user',
                'content': (
                    '[Question 3] - Why is it hard?\n\n'
                    'Discuss the challenges and complexities involved in solving this problem.\n'
                    'Explain why naive or straightforward approaches may fail.\n'
                    'Identify any technical, theoretical, or practical obstacles that need to be overcome. MAKE IT CLEAR.\n\n'
                    'Response in 100 words. Use declarative sentences instead of interrogative ones. Ground on related papers and use [1], [2], ... to refer to them. Please ensure that no identical citations point to different URLs, and no different citations point to the same URL.'
                ),
            }
        )

        response = self.client.run(
            agent=self.leader,
            messages=messages,
            context_variables={'papers': final_related_papers},
        )

        q3 = response.messages[-1]['content']
        messages.extend(response.messages)

        messages.append(
            {
                'role': 'user',
                'content': (
                    "[Question 4] - Why hasn't it been solved before?\n\n"
                    'Identify gaps or limitations in previous research or existing solutions.\n'
                    'Discuss any barriers that have prevented this problem from being solved until now.\n'
                    'Explain how your approach differs from or improves upon prior work. MAKE IT CLEAR.\n\n'
                    'Response in 100 words. Use declarative sentences instead of interrogative ones. Ground on related papers and use [1], [2], ... to refer to them. Please ensure that no identical citations point to different URLs, and no different citations point to the same URL.'
                ),
            }
        )

        response = self.client.run(
            agent=self.leader,
            messages=messages,
            context_variables={'papers': final_related_papers},
        )

        q4 = response.messages[-1]['content']
        messages.extend(response.messages)

        messages.append(
            {
                'role': 'user',
                'content': (
                    '[Question 5] - What are the key components of my approach and results?\n\n'
                    'Outline your proposed methodology in detail, including the method, dataset, metric that you plan to use.\n'
                    'Describe the expected outcomes. MAKE IT CLEAR.\n\n'
                    'Response in 100 words. Use declarative sentences instead of interrogative ones. Ground on related papers and use [1], [2], ... to refer to them. Please ensure that no identical citations point to different URLs, and no different citations point to the same URL.'
                ),
            }
        )

        response = self.client.run(
            agent=self.leader,
            messages=messages,
            context_variables={'papers': final_related_papers},
        )

        q5 = response.messages[-1]['content']
        messages.extend(response.messages)

        proposal = Proposal(q1=q1, q2=q2, q3=q3, q4=q4, q5=q5)

        yield proposal, self.leader
        self.proposals.append(proposal)
