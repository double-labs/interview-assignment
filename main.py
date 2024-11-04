import os
import random
import time
from datetime import datetime
from typing import Optional
from typing import cast

from loguru import logger
from playwright.sync_api import Page
from pydantic import BaseModel
from pydantic import Field

from browsergym.core.env import BrowserEnv
from browsergym.workarena.tasks.list import FilterHardwareListTask

from axtree import flatten_axtree_to_str


class TaskResult(BaseModel):
    task_name: str
    seed: Optional[int]
    success: bool
    duration: float
    exception: Optional[str]


class EvaluationResult(BaseModel):
    task_results: list[TaskResult]
    failed_to_setup: list[str] = Field(default=[])

    def record_result(self, result: TaskResult) -> None:
        self.task_results.append(result)

    def record_setup_failure(self, task: str, config_index: int) -> None:
        self.failed_to_setup.append(f"{task} | Config Index: {config_index}")

    @property
    def average_task_duration(self) -> float:
        if not self.task_results:
            return 0
        return sum([task.duration for task in self.task_results]) / len(self.task_results)

    @property
    def succeeded_tasks(self) -> int:
        return len([task for task in self.task_results if task.success])

    @property
    def completed_tasks(self) -> int:
        return len([task for task in self.task_results if not task.exception])

    @property
    def naturally_failed_tasks(self) -> int:
        """
        Tasks that failed due to the agent not being able to complete them,
        as opposed to tasks that failed due to an exception
        """
        return len([task for task in self.task_results if not task.success and not task.exception])

    @property
    def failed_tasks_due_to_exception(self) -> int:
        return len([task for task in self.task_results if task.exception])

    def display(self, cur_logger) -> None:
        cur_logger.info("----------------")
        cur_logger.info("Evaluation Results")
        cur_logger.info("----------------")
        cur_logger.info(
            f"Total success rate: "
            f"{round(
                self.succeeded_tasks / (len(self.task_results) + len(self.failed_to_setup)), 2
            ) * 100}%"
        )
        cur_logger.info(
            f"Total success rate no failed: "
            f"{round(self.succeeded_tasks / len(self.task_results), 2) * 100}%"
        )
        cur_logger.info(f"Total Tasks: {len(self.task_results)}")
        cur_logger.info(f"Tasks failed to setup: {len(self.failed_to_setup)}")
        cur_logger.info(
            f"""From {self.completed_tasks} fully completed tasks | Succeeded Tasks:
            {self.succeeded_tasks} | failed tasks: {self.naturally_failed_tasks}"""
        )
        cur_logger.info(f"Failed tasks due to exception: {self.failed_tasks_due_to_exception}")
        cur_logger.info(f"Average Task Duration: {self.average_task_duration:.2f} seconds")
        cur_logger.info("----------------")
        if self.failed_to_setup:
            cur_logger.info("\n- ".join(["Tasks that failed to setup:"] + self.failed_to_setup))


def setup_env(
    task: type,
    headless: bool,
    seed: Optional[int],
    config: Optional[dict] = None,
) -> tuple[BrowserEnv, dict[str, str]]:
    if not config:
        config = {}
    for setup_attempt in range(3):
        env = BrowserEnv(
            task_entrypoint=task,
            headless=headless,
            task_kwargs=config,
        )
        try:
            obs, _ = env.reset(seed)
            return (env, obs)
        except Exception as e:
            logger.opt(exception=e).warning(f"Failed to setup task: {e}")
            try:
                env.close()
            except Exception as e:
                logger.opt(exception=e).warning("Failed to close environment")
            time.sleep(2 * setup_attempt)
    raise Exception("Failed to setup task after multiple retries")


def run_seed(
    task: type,
    eval_folder: str,
    seed: Optional[int],
    headless: bool = True,
    config: Optional[dict] = None,
):
    if not config:
        config = {}
    if not seed:
        seed = random.randint(0, 1000)
    task_folder = create_task_folder(eval_folder, task, seed)
    cur_logging_hander_id = logger.add(os.path.join(task_folder, "execution_trace.log"))
    obs = {}
    try:
        env, obs = setup_env(task, headless, seed, config)
    except Exception as e:
        logger.opt(exception=e).warning("Failed to setup task after multiple retries")
        logger.remove(cur_logging_hander_id)
        return TaskResult(
            task_name=task.__name__,
            success=False,
            duration=0,
            exception=str(e),
            seed=seed,
        )
    env = cast(BrowserEnv, env)  # type: ignore
    logger.info(f"Goal: {obs['goal']} | URL: {obs['url']}")

    success = False
    exception = None
    step = 0
    now = datetime.now()
    page = cast(Page, env.get_wrapper_attr("page"))
    height = page.viewport_size["height"] if page.viewport_size else 1080
    width = page.viewport_size["width"] if page.viewport_size else 1920
    page.set_viewport_size({"width": width, "height": int(height * 2)})
    MAX_STEPS = 16
    while step < MAX_STEPS:
        screenshot_save_path = os.path.join(task_folder, f"screenshot_{step}.jpeg")
        with open(screenshot_save_path, "wb") as f:
            f.write(page.screenshot(full_page=True, timeout=60000, type="jpeg"))
        axt_save_path = os.path.join(task_folder, f"axt_{step}.txt")
        with open(axt_save_path, "w") as f:
            f.write(flatten_axtree_to_str(obs["axtree_object"]))
        try:
            action = "noop()"
            input("Press enter to parse the page")
            obs, reward, terminated, truncated, _ = env.step(action)
            step += 1
        except Exception as e:
            logger.opt(exception=e).warning("Error executing action:")
            exception = str(e)
            break
        cast(float, reward)
        if reward == 1:
            success = True

        done = terminated or truncated
        if done:
            page = cast(Page, env.get_wrapper_attr("page"))
            screenshot_save_path = os.path.join(task_folder, "screenshot_last.jpeg")
            with open(screenshot_save_path, "wb") as f:
                f.write(page.screenshot(full_page=True, timeout=60000, type="jpeg"))

            axt_save_path = os.path.join(task_folder, "axt_last.txt")
            with open(axt_save_path, "w") as f:
                f.write(obs["axtree_object"])
            break

    env.close()
    task_duration = (datetime.now() - now).seconds
    result = TaskResult(
        task_name=task.__name__,
        success=success,
        duration=task_duration,
        exception=exception,
        seed=seed,
    )
    logger.info(f"Task: {task} | seed: {seed} | Success: {success}")
    logger.remove(cur_logging_hander_id)
    return result


def create_eval_folder() -> str:
    save_folder_path = os.path.join(
        os.path.dirname(__file__),
        "results",
        f"eval_results_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}",
    )
    os.makedirs(save_folder_path, exist_ok=True)
    return save_folder_path


def create_task_folder(eval_folder_path: str, task: type, seed: int) -> str:
    task_folder = os.path.join(eval_folder_path, f"{task.__name__}_{seed}")
    os.makedirs(task_folder, exist_ok=True)
    return task_folder


def main() -> None:
    """
    Runs browsergym tasks with the twin agent
    Relies on the browsergym implementation of their AXT parsing
    """
    os.environ["SNOW_INSTANCE_URL"]= "https://dev199980.service-now.com/"
    os.environ["SNOW_INSTANCE_UNAME"] = "admin"
    os.environ["SNOW_INSTANCE_PWD"] = "w!nEqZ6w8+WJ"
    eval_folder_path = create_eval_folder()
    logger.add(os.path.join(eval_folder_path, "full_evaluation_trace.log"))
    run_seed(
        FilterHardwareListTask,
        eval_folder_path,
        headless=False,
        seed=10,
    )


if __name__ == "__main__":
    main()
