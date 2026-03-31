import json
import logging
import threading
from typing import List, Optional

from camel.memories.base import MemoryBlock, AgentMemory, BaseContextCreator
from camel.memories.records import MemoryRecord, ContextRecord
from camel.memories.blocks import ChatHistoryBlock
from camel.types import OpenAIBackendRole
from hindsight_client import Hindsight

logger = logging.getLogger(__name__)

class HindsightMemoryBlock(MemoryBlock):
    def __init__(self, client: Hindsight, bank_id: str) -> None:
        self.client = client
        self.bank_id = bank_id
        # Store connection details for creating per-thread clients (aiohttp event loop safety)
        self._base_url: str = str(client._api_client.configuration.host)
        try:
            # We try to create the bank, it may fail if it already exists
            self.client.create_bank(self.bank_id)
        except Exception as e:
            logger.debug(f"Bank creation error (might already exist): {e}")

    def write_records(self, records: List[MemoryRecord]) -> None:
        if not records:
            return
            
        items = []
        for record in records:
            content = record.message.content
            if not content:
                continue
            
            # Keep original record intact and save it as JSON in metadata
            record_dict = record.to_dict()
            metadata = {
                "record_dict": json.dumps(record_dict)
            }
            items.append({
                "content": content,
                "metadata": metadata
            })

        logger.info(f"Retaining {len(items)} records in bank {self.bank_id}")
        _err: List[Optional[Exception]] = [None]

        # Create a fresh Hindsight client per thread to avoid aiohttp/asyncio event loop
        # conflicts: the ApiClient's session is bound to the loop of its creation thread.
        _base_url = self._base_url
        _bank_id = self.bank_id

        def _do_retain() -> None:
            _thread_client = Hindsight(base_url=_base_url, api_key="dummy_key")
            try:
                _thread_client.retain_batch(_bank_id, items)
            except Exception as exc:
                _err[0] = exc

        t = threading.Thread(target=_do_retain, daemon=True)
        t.start()
        t.join(timeout=30)
        if t.is_alive():
            logger.warning(
                f"retain_batch timed out after 30s for bank {self.bank_id} — "
                "skipping, background consolidation may still complete"
            )
        elif _err[0] is not None:
            logger.error(f"Failed to retain records: {_err[0]}")
        else:
            logger.info("Retain successful")

    def retrieve(self, keyword: str, limit: int = 3) -> List[ContextRecord]:
        if not keyword:
            return []
            
        context_records = []
        try:
            response = self.client.recall(
                bank_id=self.bank_id,
                query=keyword,
                max_tokens=2048
            )
            for res in response.results:
                if not res.metadata or "record_dict" not in res.metadata:
                    continue
                    
                record_json = res.metadata["record_dict"]
                try:
                    record_dict = json.loads(record_json)
                    mem_record = MemoryRecord.from_dict(record_dict)
                    context_records.append(ContextRecord(
                        memory_record=mem_record,
                        score=1.0, 
                        timestamp=mem_record.timestamp,
                    ))
                except Exception as e:
                    logger.error(f"Failed to reconstruct MemoryRecord: {e}")
        except Exception as e:
            logger.error(f"Failed to recall records: {e}")
                
        return context_records[:limit]

    def clear(self) -> None:
        try:
            self.client.delete_bank(self.bank_id)
            self.client.create_bank(self.bank_id)
        except Exception as e:
            logger.error(f"Failed to clear bank {self.bank_id}: {e}")

    def pop_records(self, count: int) -> List[MemoryRecord]:
        raise NotImplementedError("pop_records not supported in Hindsight")

    def remove_records_by_indices(self, indices: List[int]) -> List[MemoryRecord]:
        raise NotImplementedError("remove_records_by_indices not supported in Hindsight")

class HindsightAgentMemory(AgentMemory):
    def __init__(
        self,
        context_creator: BaseContextCreator,
        hindsight_block: HindsightMemoryBlock,
        chat_history_block: Optional[ChatHistoryBlock] = None,
        retrieve_limit: int = 3,
        agent_id: Optional[str] = None,
    ) -> None:
        self.hindsight_block = hindsight_block
        self.chat_history_block = chat_history_block or ChatHistoryBlock()
        self.retrieve_limit = retrieve_limit
        self._context_creator = context_creator
        self._current_topic: str = ""
        self._agent_id = agent_id

    @property
    def agent_id(self) -> Optional[str]:
        return self._agent_id

    @agent_id.setter
    def agent_id(self, val: Optional[str]) -> None:
        self._agent_id = val

    def get_context_creator(self) -> BaseContextCreator:
        return self._context_creator

    def retrieve(self) -> List[ContextRecord]:
        chat_history = self.chat_history_block.retrieve()
        hindsight_retrieve = self.hindsight_block.retrieve(
            keyword=self._current_topic,
            limit=self.retrieve_limit,
        )
        # Assuming index 0 is system message, insert Hindsight context after it
        if len(chat_history) > 0:
            return chat_history[:1] + hindsight_retrieve + chat_history[1:]
        else:
            return hindsight_retrieve

    def write_records(self, records: List[MemoryRecord]) -> None:
        self.hindsight_block.write_records(records)
        self.chat_history_block.write_records(records)

        for record in records:
            if record.role_at_backend == OpenAIBackendRole.USER:
                self._current_topic = record.message.content

    def clear(self) -> None:
        self.chat_history_block.clear()
        self.hindsight_block.clear()

    def pop_records(self, count: int) -> List[MemoryRecord]:
        return self.chat_history_block.pop_records(count)

    def remove_records_by_indices(self, indices: List[int]) -> List[MemoryRecord]:
        return self.chat_history_block.remove_records_by_indices(indices)
